"""FUT-05: exact revisioned vendor offers and non-overlapping billable sources.

CatalogItem/CatalogRevision give immutable commercial history. CampaignPricingPin
binds chosen OFFER revisions to exact pinned technical participants; rate changes
never mutate past snapshots. No run billing/FX or pooled-credit accounting here.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from .models import CatalogItem, CatalogRevision, CampaignPricingPin
from .catalog_services import create_component, revise_component, RevisionConflict

KINDS = frozenset({"model", "provider", "harness", "framework"})
ACCESS = frozenset({"accessible", "restricted", "not_accessible", "unknown"})
FAMILIES = frozenset({"free", "token", "credit", "request", "time", "usage",
                      "tiered", "subscription", "per_seat", "hybrid", "negotiated"})
CHARGES = frozenset({"free", "fixed", "variable", "unknown"})
METERS = frozenset({"input_tokens", "output_tokens", "cached_input_tokens",
                    "reasoning_tokens", "requests", "seconds", "minutes",
                    "hours", "jobs", "executions", "provider_credits",
                    "gpu_hours", "custom_units"})
PERIODS = frozenset({"month", "year", "seat_month", "seat_year", "one_off"})
STATUSES = frozenset({"active", "retired", "unknown"})


class InvalidPricing(ValueError):
    pass


def _nonempty(value, field, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise InvalidPricing(field + " must be a nonempty string")
    return value.strip()


def _decimal(value, field, allow_none=False):
    if allow_none and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise InvalidPricing(field + " requires an explicit finite nonnegative decimal")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise InvalidPricing(field + " is not a decimal") from None
    if not number.is_finite() or number < 0:
        raise InvalidPricing(field + " must be finite and nonnegative")
    return number


def _date(value, field, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise InvalidPricing(field + " must be ISO YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidPricing(field + " must be ISO YYYY-MM-DD") from None


def accessibility(properties):
    if not isinstance(properties, dict):
        return "unknown"
    value = properties.get("enterprise_accessibility", "unknown")
    return value if isinstance(value,str) and value in ACCESS else "unknown"


def validate_offer(data):
    if not isinstance(data, dict):
        raise InvalidPricing("Offer must have structured properties")
    if set(data)-{"component_id", "billing_owner", "currency", "source",
                  "checked_on", "effective_from", "effective_to", "status",
                  "terms", "tax_treatment", "lines", "applicability"}:
        raise InvalidPricing("Unsupported pricing fields")
    component_id = _nonempty(data.get("component_id"), "component_id", 120)
    owner = CatalogItem.objects.filter(public_id=component_id, type_slug__in=KINDS).first()
    if owner is None or owner.current_revision_id is None:
        raise InvalidPricing("Offer must reference one existing real technology component")
    billing_owner = _nonempty(data.get("billing_owner"), "billing_owner")
    currency = _nonempty(data.get("currency"), "currency", 3).upper()
    if len(currency) != 3 or not currency.isalpha():
        raise InvalidPricing("Explicit three-letter ISO currency is required")
    source = _nonempty(data.get("source"), "source", 2048)
    checked_on = _date(data.get("checked_on"), "checked_on")
    start = _date(data.get("effective_from"), "effective_from", True)
    end = _date(data.get("effective_to"), "effective_to", True)
    if start and end and end < start:
        raise InvalidPricing("effective_to precedes effective_from")
    if data.get("status") not in STATUSES:
        raise InvalidPricing("Offer requires active, retired or unknown status")
    if not isinstance(data.get("terms", ""), str) or len(data.get("terms", "")) > 4000:
        raise InvalidPricing("Terms exceed maximum length")
    if data.get("tax_treatment", "unknown") not in ("included", "excluded", "unknown"):
        raise InvalidPricing("Invalid tax treatment")
    applicability = data.get("applicability", {})
    if not isinstance(applicability, dict) or len(str(applicability)) > 3000:
        raise InvalidPricing("Applicability must be a bounded JSON object")
    lines = data.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 32:
        raise InvalidPricing("An offer requires 1-32 cumulative charge lines")
    ids = set()
    for line in lines:
        if not isinstance(line, dict) or set(line)-{"charge_id", "family",
                "charge_type", "meter", "rate", "unit_size", "period", "tiers",
                "provider_credit_namespace", "conditions"}:
            raise InvalidPricing("Unsupported charge-line fields")
        charge_id = _nonempty(line.get("charge_id"), "charge_id", 150)
        if charge_id in ids:
            raise InvalidPricing("Duplicate charge identity in one offer")
        ids.add(charge_id)
        if line.get("family") not in FAMILIES or line.get("charge_type") not in CHARGES:
            raise InvalidPricing("Unknown pricing family or charge type")
        kind = line["charge_type"]
        if kind == "fixed":
            if line.get("period") not in PERIODS:
                raise InvalidPricing("Fixed charges require explicit billing period")
            _decimal(line.get("rate"), "fixed rate")
        elif kind == "variable":
            if line.get("meter") not in METERS:
                raise InvalidPricing("Variable charge requires a known meter")
            _decimal(line.get("unit_size"), "unit_size")
            if _decimal(line.get("unit_size"), "unit_size") <= 0:
                raise InvalidPricing("unit_size must be positive")
            if line.get("meter") == "provider_credits":
                _nonempty(line.get("provider_credit_namespace"), "provider_credit_namespace")
            if line.get("rate") is not None:
                _decimal(line.get("rate"), "variable rate")
            if line.get("family") == "tiered":
                tiers = line.get("tiers")
                if not isinstance(tiers, list) or not tiers:
                    raise InvalidPricing("Tiered charge requires explicit tiers")
                last = Decimal("-1")
                for tier in tiers:
                    if not isinstance(tier, dict) or set(tier)!={"up_to", "rate"}:
                        raise InvalidPricing("Each tier requires up_to and rate")
                    upper = _decimal(tier["up_to"], "tier upper", allow_none=True)
                    _decimal(tier["rate"], "tier rate")
                    if last is None or (upper is not None and upper <= last):
                        raise InvalidPricing("Tier limits must strictly increase")
                    last = upper
        elif kind == "free":
            if line.get("rate") not in (None, 0, "0", "0.0"):
                raise InvalidPricing("Free line cannot carry nonzero rate")
        elif kind == "unknown" and line.get("rate") is not None:
            raise InvalidPricing("Unknown charge must not invent rate")
        if not isinstance(line.get("conditions", {}), dict):
            raise InvalidPricing("Charge conditions must be a JSON object")
    return data


def readiness(offer_revision):
    data = offer_revision.properties
    reasons = []
    if data.get("status") != "active":
        reasons.append("offer not active")
    start, end = data.get("effective_from"), data.get("effective_to")
    today = date.today().isoformat()
    if start and start > today or end and end < today:
        reasons.append("offer outside effective dates")
    required = []
    fixed = []
    for line in data.get("lines", []):
        if line["charge_type"] == "unknown":
            reasons.append("unknown charge: " + line["charge_id"])
        if line["charge_type"] == "variable":
            if line.get("rate") is None and line.get("family") != "tiered":
                reasons.append("missing variable rate: " + line["charge_id"])
            required.append({"charge_id": line["charge_id"], "meter": line["meter"],
                "unit_size": line["unit_size"], "currency": data["currency"],
                "credit_namespace": line.get("provider_credit_namespace")})
        if line["charge_type"] == "fixed":
            fixed.append({"charge_id":line["charge_id"], "period":line["period"],
                          "rate":line["rate"], "currency":data["currency"]})
    return {"complete":not reasons, "reasons":reasons,
            "required_meters":required, "fixed_commitments":fixed}


def offer_record(item, rev=None):
    rev = rev or item.current_revision
    return {"id":item.public_id, "revision":f"r{rev.number:03d}",
            "revision_id":str(rev.id), "name":rev.display_name,
            "properties":rev.properties, "readiness":readiness(rev),
            "created_at":rev.created_at.isoformat(),
            "created_by":rev.created_by.get_username()}


def offer_create(*, actor, name, properties):
    validate_offer(properties)
    return create_component(type_slug="pricing_offer", actor=actor,
                            name=name, properties=properties)


def offer_revise(*, actor, item, expected_revision, name, properties):
    validate_offer(properties)
    if properties["component_id"] != item.current_revision.properties["component_id"]:
        raise InvalidPricing("Offer commercial owner cannot change; create another offer")
    return revise_component(item=item,type_slug="pricing_offer",actor=actor,
                            expected_revision=expected_revision,name=name,properties=properties)


def source_map(ctx):
    """Describe a pinned technical setup without inventing Task-centred candidates."""
    available = {}
    for kind, component, _ in ctx["components"]:
        available["root:" + kind] = component
    if ctx["framework"] is not None:
        available["root:framework"] = ctx["framework"]
    for participant in ctx["participants"]:
        if participant["identity"] is not None:
            pid = participant["identity"].public_id
            for kind, (component, _) in participant["components"].items():
                available[pid + ":" + kind] = component
    return available


def prepare_selections(rows, ctx, previous=None):
    """Validate exact vendor revisions inside campaign's existing atomic edit.

    Empty selection is legal as an INCOMPLETE plan, not a runnable pricing gate.
    Omitted field on an unchanged context retains the same immutable pins.
    """
    available = source_map(ctx)
    if rows is None and previous is not None:
        rows = [{"source_key":p.source_key,"component_id":p.component.public_id,
                 "offer_id":p.offer.public_id,"offer_revision_id":str(p.offer_revision_id)}
                for p in previous.pricing_pins.select_related("component","offer")]
    rows = rows or []
    if not isinstance(rows,list) or len(rows)>256:
        raise InvalidPricing("Pricing selections must be a bounded array")
    pinned = []
    sources = set()
    billed = set()
    for selection in rows:
        if not isinstance(selection,dict) or set(selection)!={"source_key","component_id",
                                                               "offer_id","offer_revision_id"}:
            raise InvalidPricing("Each selection requires exact source, component, offer and revision")
        key = selection["source_key"]
        if not isinstance(key,str) or key not in available:
            raise InvalidPricing("Pricing selection does not belong to current campaign configuration")
        component = available[key]
        if selection["component_id"] != component.public_id or key in sources:
            raise InvalidPricing("Wrong or duplicate billable source")
        sources.add(key)
        offer = CatalogItem.objects.filter(public_id=selection["offer_id"],
                                            type_slug="pricing_offer").first()
        if offer is None or not offer.current_revision:
            raise InvalidPricing("Unknown pricing offer")
        rev = CatalogRevision.objects.filter(pk=selection["offer_revision_id"],item=offer).first()
        if rev is None or rev.properties.get("component_id")!=component.public_id:
            raise InvalidPricing("Offer revision is not applicable to selected component")
        if offer.current_revision_id != rev.pk and previous is None:
            # Brand-new plans may deliberately pin an older still-valid version
            # only if it was manually selected in the UI; do not override.
            pass
        for line in rev.properties.get("lines", []):
            # A charge belongs to one invocation; separate Framework participants
            # can make independent invocations under the same vendor tariff.
            # Root model/provider describing the SAME invoice may not duplicate it.
            identity = (key.split(":")[0],rev.properties["billing_owner"], line["charge_id"])
            if identity in billed:
                raise InvalidPricing("Duplicate underlying invoice charge across Model/Provider/participants")
            billed.add(identity)
        pinned.append((key,component,offer,rev))
    return pinned


def pricing_status(snapshot):
    required = {}
    for pin in snapshot.component_pins.select_related("component"):
        required["root:"+pin.kind] = pin.component.public_id
    if snapshot.framework_id:
        required["root:framework"] = snapshot.framework.public_id
    for participant in snapshot.participant_pins.select_related("participant","model","provider","harness"):
        for kind in ("model","provider","harness"):
            required[participant.participant.public_id+":"+kind] = getattr(participant,kind).public_id
    pins=list(snapshot.pricing_pins.select_related("component","offer","offer_revision"))
    chosen={p.source_key:p for p in pins}
    reasons=[]
    missing = sorted(set(required)-set(chosen))
    if missing:
        reasons.append("Unselected source(s): "+", ".join(missing))
    meters=[]
    fixed=[]
    for pin in pins:
        s=readiness(pin.offer_revision)
        if not s["complete"]:
            reasons.extend(pin.source_key+": "+msg for msg in s["reasons"])
        meters.extend(dict(m,source_key=pin.source_key) for m in s["required_meters"])
        fixed.extend(dict(f,source_key=pin.source_key) for f in s["fixed_commitments"])
    if not required:
        reasons.append("No explicit technical configuration priced")
    return {"complete":not reasons,"reasons":reasons,
            "required_sources":required, "missing_sources":missing,
            "required_meters":meters,"fixed_commitments":fixed,
            "currency_set":sorted({p.offer_revision.properties["currency"] for p in pins})}


def serialize_selections(snapshot):
    return [{"source_key":p.source_key, "component_id":p.component.public_id,
             "offer_id":p.offer.public_id, "offer_revision_id":str(p.offer_revision_id),
             "offer_revision":f"r{p.offer_revision.number:03d}"}
            for p in snapshot.pricing_pins.select_related("component","offer","offer_revision")
            .order_by("source_key")]
