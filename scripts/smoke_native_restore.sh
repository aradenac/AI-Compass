#!/usr/bin/env bash
# CI-only source -> isolated target; never run on a user's operational stack.
set -Eeuo pipefail
if [[ "$GITHUB_ACTIONS" != "true" || "$CI" != "true" ]]; then
  echo "Disposable archive roundtrip is CI-only" >&2
  exit 2
fi
cd "$(dirname "$BASH_SOURCE")/.."
export STAGING_CANDIDATE="$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
export STAGING_DB_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
export STAGING_DJANGO_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
export STAGING_PORT=18081
export STAGING_PAGE="$PWD/prototype.html"
project="ai-compass-native-ci-$STAGING_CANDIDATE"
stage() { docker compose -f staging/compose.yaml -p "$project" "$@"; }
cleanup() {
  stage down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f /tmp/ai-native-restore-smoke.zip
}
trap cleanup EXIT
source_id="$(docker compose ps -q api)"
docker compose exec -T api python manage.py shell -c \
  'from config.archive_services import build_native_export; import shutil; a=build_native_export(); f=open("/tmp/native-source-smoke.zip","wb"); shutil.copyfileobj(a,f); f.close(); a.close()'
docker cp "$source_id:/tmp/native-source-smoke.zip" /tmp/ai-native-restore-smoke.zip
python3 scripts/verify_export.py /tmp/ai-native-restore-smoke.zip
stage up -d --wait --build db api
stage exec -T api python manage.py migrate --noinput
stage exec -T api python manage.py bootstrap_identity
password="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
printf '%s\n' "$password" | stage exec -T api python manage.py bootstrap_identity \
  --username native-ci-operator --role data-maintainer --password-stdin
unset password
target_id="$(stage ps -q api)"
docker cp /tmp/ai-native-restore-smoke.zip "$target_id:/tmp/native-source-smoke.zip"
restore() {
  stage exec -T -e AI_COMPASS_NATIVE_RESTORE_TEST=1 api python manage.py \
    restore_native_archive /tmp/native-source-smoke.zip --operator native-ci-operator --json "$@"
}
restore --preview
restore --apply
restore --apply | python3 -c 'import sys,json; assert json.load(sys.stdin)["status"]=="already_imported"'
stage exec -T api python manage.py shell -c \
  'from config.models import CatalogRevision,CatalogItem,EvidenceBlob; from config.evidence_store import verify_bytes; from restore_tracking.models import NativeRestore; assert CatalogItem.objects.count()>0 and CatalogRevision.objects.count()>0; [verify_bytes(b.sha256,size=b.size) for b in EvidenceBlob.objects.all()]; assert NativeRestore.objects.filter(state="committed").count()==1'
stage exec -T api python manage.py shell -c \
  'from config.catalog_services import create_model; from django.contrib.auth import get_user_model; u=get_user_model().objects.get(username="native-ci-operator"); create_model(actor=u,name="local divergence",properties={"context_window":2048})'
if restore --apply; then
  echo "Unsafe restore replay allowed divergent history" >&2
  exit 1
fi
echo "Native archive isolated restore, exact replay and drift refusal passed"
