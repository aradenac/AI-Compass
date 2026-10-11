#!/usr/bin/env bash
# Prepare pinned public images in parallel on each disposable CI runner.
set -euo pipefail

sudo install -d -m 0755 /etc/docker
echo '{"registry-mirrors":["https://mirror.gcr.io"]}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
docker info --format '{{json .RegistryConfig.Mirrors}}'

pull_one() {
  local image="$1" attempt
  for attempt in 1 2 3 4 5; do
    if docker pull "public.ecr.aws/docker/library/${image}"; then
      docker tag "public.ecr.aws/docker/library/${image}" "${image}"
      return 0
    fi
    sleep "$((attempt * 6))"
  done
  echo "ECR pull failed for ${image} after retries" >&2
  return 1
}

pids=()
for image in postgres:17-alpine caddy:2-alpine python:3.12-slim busybox:1.36; do
  pull_one "$image" &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
exit "$failed"
