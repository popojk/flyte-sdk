"""
App with a mounted PersistentVolumeClaim — exercises K8sPod app payload support.

This example is a functional test for the backend change that implements the
``Spec_Pod`` (K8sPod) case in ``buildPodSpec`` (flyteorg/flyte PR #7340,
resolving the AppEnvironment PVC gap in issue #7702).

Passing a ``pod_template`` to an ``AppEnvironment`` makes the SDK serialize the
app as a **K8sPod** payload (``Spec.pod``) instead of the plain ``Container``
payload. That path used to fail on the backend with
``"K8sPod app payload is not yet supported"``; with the PR it deserializes the
pod spec — including ``volumes`` / ``volumeMounts`` — so an app can mount a
pre-existing PVC (e.g. warm model weights) instead of baking them into the image
or downloading on every cold start.

What it does
------------
Mounts ``PVC_CLAIM_NAME`` read-only at ``MOUNT_PATH`` and serves a directory
listing of it over HTTP. If the PVC mounted, browsing the app URL shows the
files on the volume — that's the pass/fail signal.

Prerequisites
-------------
1. The PVC must already exist in the app namespace, e.g.::

       kubectl -n flyte apply -f - <<'EOF'
       apiVersion: v1
       kind: PersistentVolumeClaim
       metadata:
         name: my-model-pvc
       spec:
         accessModes: ["ReadWriteOnce"]
         resources:
           requests:
             storage: 1Gi
       EOF

   (Populate it with some files first so the listing is non-empty.)

2. Knative must allow PVCs — enable the feature flag in ``config-features``::

       kubectl -n knative-serving patch configmap/config-features --type merge \
         -p '{"data":{"kubernetes.podspec-persistent-volume-claim":"enabled"}}'

   Without this, Knative's webhook rejects the KService even though the spec
   deserializes correctly.

Gotcha
------
For apps the SDK requires the primary container to be named ``"app"`` (unlike
tasks, which use ``"primary"``). Both ``primary_container_name`` and the
``V1Container.name`` below must be ``"app"`` or serialization raises.
"""

import flyte
from flyte.app import AppEnvironment
from kubernetes.client import (
    V1Container,
    V1PersistentVolumeClaimVolumeSource,
    V1PodSpec,
    V1Volume,
    V1VolumeMount,
)

# The pre-existing PVC to mount (see prerequisites above).
PVC_CLAIM_NAME = "my-model-pvc"
MOUNT_PATH = "/models"

# pod_template with a PVC volume -> serialized as the K8sPod app payload.
pod_template = flyte.PodTemplate(
    # Must be "app" for AppEnvironment (SDK requirement); tasks use "primary".
    primary_container_name="app",
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="app",  # image / args / resources are merged in from the AppEnvironment
                volume_mounts=[
                    V1VolumeMount(name="model", mount_path=MOUNT_PATH, read_only=True),
                ],
            ),
        ],
        volumes=[
            V1Volume(
                name="model",
                persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                    claim_name=PVC_CLAIM_NAME,
                    read_only=True,
                ),
            ),
        ],
    ),
)

env = AppEnvironment(
    name="pvc-mount-app",
    # The app runtime re-imports this module (via AppEnvResolver) to load `env`,
    # so `kubernetes` (imported at module top for V1PodSpec etc.) must be present
    # in the image too — not just locally at deploy time.
    image=flyte.Image.from_debian_base().with_pip_packages("kubernetes"),
    # Serve a directory listing of the mounted PVC. A non-empty listing at the
    # app URL means the volume mounted successfully.
    args=f"python -m http.server 8080 --directory {MOUNT_PATH}",
    port=8080,
    resources=flyte.Resources(cpu=1, memory="1Gi"),
    pod_template=pod_template,
    requires_auth=False,
    # Apple-Silicon devbox workaround: the VM advertises SVE via HWCAP but can't
    # execute it, so the flyte runtime's OpenSSL/cryptography import SIGILLs
    # (exit 132) before the app starts. Force OpenSSL's generic code paths.
    env_vars={"OPENSSL_armcap": "0"},
)

if __name__ == "__main__":
    flyte.init_from_config()
    deployment = flyte.serve(env)
    print(f"App deployed at: {deployment.url}")
    print(f"Browse it — a directory listing of {MOUNT_PATH} means the PVC '{PVC_CLAIM_NAME}' mounted.")
