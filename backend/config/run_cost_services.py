"""FUT-09: deterministic, immutable-reference tariff-driven consumption contracts.

A price is quoted per original source and original offer revision, never by
looking up today's catalog rates. No global quotas, prepaid wallet or FX
conversion is inferred. Monetary decimals are serialized as strings.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from .pricing_services import readiness

POLICY = "reference-usage-v1"
LIMIT = Decimal("1000000000000000")


class MissingMeter(ValueError):
    pass


class InvalidMeter(ValueError):
    pass


def decimal(value, label):
    if isinstance(value, bool) or value is None or not isinstance(value, (int,float,str)):
        raise InvalidMeter(label+" needs an explicit nonnegative number")
    try:
        number=Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise InvalidMeter(label+" is not a decimal") from None
    if not number.is_finite() or number < 0 or number > LIMIT:
        raise InvalidMeter(label+" must be finite, nonnegative and bounded")
    return number


def _pins(session):
    """A trial cannot incur consumption for *unselected* Framework participants."""
    if session.pricing_pins.exists():
        rows=session.pricing_pins.select_related("offer","offer_revision").order_by("source_key")
    elif session.campaign_snapshot.revision.properties.get("pricing_policy")=="offer_revisions_v1":
        rows=session.campaign_snapshot.pricing_pins.select_related(
            "offer","offer_revision").order_by("source_key")
    else:
        return None
    selected=set(session.selected_participants or [])
    return [p for p in rows if p.source_key.startswith("root:") or
            p.source_key.split(":")[0] in selected]


def contract(session):
    pins=_pins(session)
    if pins is None:return None
    required=[];fixed=[];sources=[];reasons=[]
    seen=set()
    for p in pins:
        prop=p.offer_revision.properties
        status=readiness(p.offer_revision)
        if not status["complete"]:
            reasons.extend(p.source_key+": "+s for s in status["reasons"])
        for line in prop.get("lines",[]):
            if line.get("conditions"):
                reasons.append(p.source_key+"/"+line["charge_id"]+
                               ": conditional tariff requires explicit computation policy")
            if line["charge_type"]=="variable":
                key=(p.source_key,line["meter"],
                     line.get("provider_credit_namespace") if line["meter"]=="provider_credits" else None)
                if key not in seen:
                    seen.add(key)
                    required.append({"source_key":p.source_key,"meter":line["meter"],
                        "namespace":key[2],"currency":prop["currency"]})
            elif line["charge_type"]=="fixed":
                fixed.append({"source_key":p.source_key,"charge_id":line["charge_id"],
                    "rate":str(line["rate"]),"period":line["period"],"currency":prop["currency"]})
        sources.append({"source_key":p.source_key,"offer_id":p.offer.public_id,
            "offer_revision_id":str(p.offer_revision_id),
            "offer_revision":f"r{p.offer_revision.number:03d}",
            "billing_owner":prop["billing_owner"],"currency":prop["currency"]})
    if not pins:
        reasons.append("No selected reference tariff for this Run")
    return {"policy":POLICY,"complete":not reasons,"reasons":reasons,
            "required_meters":required,"fixed_commitments":fixed,"sources":sources}


def _tiers(qty, line):
    """Progressive brackets in native metered quantities (no global pooled usage)."""
    remaining=qty;lower=Decimal(0);charged=Decimal(0)
    size=decimal(line["unit_size"],"unit_size")
    if size==0:raise InvalidMeter("Price unit size cannot be zero")
    for tier in line["tiers"]:
        upper=decimal(tier["up_to"],"up_to") if tier["up_to"] is not None else None
        width=remaining if upper is None else min(remaining, upper-lower)
        if width<0:raise InvalidMeter("Invalid tier boundaries")
        rate=decimal(tier["rate"],"tier rate")
        charged+=width/size*rate
        remaining-=width
        if remaining<=0:break
        if upper is None:break
        lower=upper
    if remaining>0:
        raise MissingMeter("Tiered reference tariff has no bracket for measured quantity")
    return charged


def quote(session, observations):
    contract_data=contract(session)
    if contract_data is None:return None
    if not contract_data["complete"]:
        raise InvalidMeter("; ".join(contract_data["reasons"]))
    if not isinstance(observations,dict) or len(observations)>256:
        raise InvalidMeter("Meter values must be a bounded source-keyed JSON object")
    expected={(x["source_key"],x["meter"]) for x in contract_data["required_meters"]}
    actual=set()
    missing=[]
    for source,values in observations.items():
        if not isinstance(source,str) or not isinstance(values,dict) or len(values)>32:
            raise InvalidMeter("Each billable source needs a meter dictionary")
        for meter,value in values.items():
            if (source,meter) not in expected:
                raise InvalidMeter("Unpriced meter or source: "+str(source)+"/"+str(meter))
            decimal(value,source+"/"+meter)
            actual.add((source,meter))
    missing=sorted(expected-actual)
    if missing:
        raise MissingMeter("Unmeasured required consumption: "+", ".join(a+"/"+b for a,b in missing))
    subtotals=defaultdict(Decimal);lines=[]
    for pin in _pins(session):
        prop=pin.offer_revision.properties
        for line in prop["lines"]:
            if line["charge_type"]!="variable":continue
            qty=decimal(observations[pin.source_key][line["meter"]],
                        pin.source_key+"/"+line["meter"])
            if line["family"]=="tiered":
                amount=_tiers(qty,line)
            else:
                size=decimal(line["unit_size"],"unit_size")
                if size==0:raise InvalidMeter("Price unit size cannot be zero")
                amount=qty/size*decimal(line["rate"],"rate")
            subtotals[prop["currency"]]+=amount
            lines.append({"source_key":pin.source_key,"offer_id":pin.offer.public_id,
                "offer_revision_id":str(pin.offer_revision_id),
                "charge_id":line["charge_id"],"meter":line["meter"],
                "credit_namespace":line.get("provider_credit_namespace"),
                "quantity":str(qty),"unit_size":str(line["unit_size"]),
                "currency":prop["currency"],"amount":str(amount),
                "family":line["family"]})
    return {"policy":POLICY,
            "variable_reference_by_currency":{k:str(v) for k,v in sorted(subtotals.items())},
            "variable_charges":lines,
            "fixed_commitments":contract_data["fixed_commitments"],
            "selected_sources":contract_data["sources"],
            "observations":observations,
            "note":"Reference variable usage only; fixed fees and shared quotas not amortized; no FX inferred"}


def metering_state(session, state):
    """No silent zero: absent charge input is a pending draft, not a failed DoD."""
    schema=contract(session)
    if schema is None:return None
    submitted=state.get("metering",{})
    try:
        result=quote(session,submitted)
        return {"schema":schema,"ready":True,"missing":[],"quote":result}
    except MissingMeter as exc:
        return {"schema":schema,"ready":False,"missing":[str(exc)],"quote":None}
    except InvalidMeter as exc:
        return {"schema":schema,"ready":False,"missing":[str(exc)],"quote":None}
