from datetime import datetime, timedelta, timezone
import dateutil.parser
import humanfriendly
import kubernetes
import logging
import re
import time
import os

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
kubernetes.config.load_incluster_config()
K8S_VERSION_INFO = kubernetes.client.VersionApi().get_code()
# strip off any trailing non-numeric characters
K8S_MAJOR_VERSION = int(re.split('[^0-9]', K8S_VERSION_INFO.major)[0])
K8S_MINOR_VERSION = int(re.split('[^0-9]', K8S_VERSION_INFO.minor)[0])

SVS_CRD_GROUP = 'k8s.ryanorth.io'
SVS_CRD_VERSION = 'v1beta1'
SVS_CRD_PLURAL = 'scheduledvolumesnapshots'
VS_CRD_GROUP = 'snapshot.storage.k8s.io'
VS_CRD_VERSION = 'v1alpha1' if K8S_MAJOR_VERSION == 1 and K8S_MINOR_VERSION < 17 else 'v1beta1'
VS_CRD_PLURAL = 'volumesnapshots'
VS_CRD_KIND = 'VolumeSnapshot'

v1 = kubernetes.client.CoreV1Api()
custom_api = kubernetes.client.CustomObjectsApi()


def get_associated_snapshots(scheduled_snapshot, volume_snapshots):
    scheduled_snapshot_name = scheduled_snapshot.get('metadata', {}).get('name')
    scheduled_snapshot_pvc = scheduled_snapshot.get('spec', {}).get('persistentVolumeClaimName')
    if VS_CRD_VERSION == 'v1alpha1':
        filtered_snapshots = list(filter(
            lambda s: (
                s.get('spec', {}).get('source', {}).get('name') == scheduled_snapshot_pvc
                and s.get('spec', {}).get('source', {}).get('kind') == 'PersistentVolumeClaim'
                and s.get('metadata', {}).get('labels', {}).get('scheduled-volume-snapshot') == scheduled_snapshot_name
            ), volume_snapshots
        ))
    else:
        filtered_snapshots = list(filter(
            lambda s: (
                s.get('spec', {}).get('source', {}).get('persistentVolumeClaimName') == scheduled_snapshot_pvc
                and s.get('metadata', {}).get('labels', {}).get('scheduled-volume-snapshot') == scheduled_snapshot_name
            ), volume_snapshots
        ))
    filtered_snapshots.sort(key=lambda s: dateutil.parser.parse(
        s.get('metadata', {}).get('creationTimestamp')))
    return filtered_snapshots


def new_snapshot_needed(scheduled_snapshot, existing_snapshots):
    try:
        successful_snapshots = list(filter(
            lambda s: (
                s.get('status', {}).get('readyToUse', False)
                or not s.get('status', {}).get('error', {})
            ), existing_snapshots
        ))
        raw_snapshot_frequency = scheduled_snapshot.get('spec', {}).get('snapshotFrequency')
        if isinstance(raw_snapshot_frequency, int):
            raw_snapshot_frequency = f'{str(raw_snapshot_frequency)}h'
        snapshot_frequency_in_seconds = int(humanfriendly.parse_timespan(raw_snapshot_frequency))
        time_delta = timedelta(seconds=snapshot_frequency_in_seconds)
        snapshot_needed = (
            len(successful_snapshots) == 0
            or datetime.now(timezone.utc)
            >= (dateutil.parser.parse(successful_snapshots[-1].get('metadata', {}).get('creationTimestamp'))
                + time_delta)
        )
    except humanfriendly.InvalidTimespan:
        logging.exception(f"Unable to parse snapshotFrequency for {scheduled_snapshot.get('metadata', {}).get('name')}")
        snapshot_needed = False
    return snapshot_needed


def create_new_snapshot(scheduled_snapshot):
    pvc_name = scheduled_snapshot.get('spec', {}).get('persistentVolumeClaimName')
    new_snapshot_name = f'{pvc_name}-{str(int(time.time()))}'
    new_snapshot_namespace = scheduled_snapshot.get('metadata', {}).get('namespace')
    new_snapshot_labels = {
        **scheduled_snapshot.get('spec', {}).get('snapshotLabels', {}),
        'scheduled-volume-snapshot': scheduled_snapshot.get('metadata', {}).get('name')
    }
    logging.info(f'Creating snapshot {new_snapshot_name} in namespace {new_snapshot_namespace}')
    volume_snapshot_body = {
        'apiVersion': f'{VS_CRD_GROUP}/{VS_CRD_VERSION}',
        'kind': VS_CRD_KIND,
        'metadata': {
            'name': new_snapshot_name,
            'namespace': new_snapshot_namespace,
            'labels': new_snapshot_labels
        },
        'spec': {
            'snapshotClassName': scheduled_snapshot.get('spec', {}).get('snapshotClassName'),
        }
    }
    if VS_CRD_VERSION == 'v1alpha1':
        volume_snapshot_body['spec']['source'] = {
            'apiGroup': None,
            'kind': 'PersistentVolumeClaim',
            'name': pvc_name
        }
    else:
        volume_snapshot_body['spec']['source'] = {
            'persistentVolumeClaimName': pvc_name
        }
    try:
        custom_api.create_namespaced_custom_object(
            VS_CRD_GROUP,
            VS_CRD_VERSION,
            scheduled_snapshot.get('metadata', {}).get('namespace'),
            VS_CRD_PLURAL,
            volume_snapshot_body)
    except kubernetes.client.rest.ApiException:
        logging.exception(f'Unable to create volume snapshot {new_snapshot_name} in namespace {new_snapshot_namespace}')


def cleanup_old_snapshots(scheduled_snapshot, existing_snapshots):
    try:
        raw_snapshot_retention = scheduled_snapshot.get('spec', {}).get('snapshotRetention', -1)
        if isinstance(raw_snapshot_retention, int):
            raw_snapshot_retention = f'{str(raw_snapshot_retention)}h'
        snapshot_retention_in_seconds = int(humanfriendly.parse_timespan(raw_snapshot_retention))
    except humanfriendly.InvalidTimespan:
        logging.exception(f"Unable to parse snapshotRetention for {scheduled_snapshot.get('metadata', {}).get('name')}")
        snapshot_retention_in_seconds = -1
    if snapshot_retention_in_seconds > 0:
        oldest_retention_time = datetime.now(timezone.utc) - timedelta(seconds=snapshot_retention_in_seconds)
        for existing_snapshot in existing_snapshots:
            creation_timestamp = existing_snapshot.get('metadata', {}).get('creationTimestamp')
            if dateutil.parser.parse(creation_timestamp) < oldest_retention_time:
                snapshot_namespace = scheduled_snapshot.get(
                    'metadata', {}).get('namespace')
                snapshot_name = existing_snapshot.get(
                    'metadata', {}).get('name')
                logging.info(
                    f'Deleting snapshot {snapshot_name} from namespace {snapshot_namespace}')
                try:
                    custom_api.delete_namespaced_custom_object(
                        VS_CRD_GROUP,
                        VS_CRD_VERSION,
                        snapshot_namespace,
                        VS_CRD_PLURAL,
                        snapshot_name,
                        {})
                except kubernetes.client.rest.ApiException:
                    logging.exception(
                        f'Unable to delete volume snapshot {snapshot_name} in namespace {snapshot_namespace}')


def main():
    for namespace in v1.list_namespace().items:
        if namespace.status.phase == 'Active':
            scheduled_snapshots = custom_api.list_namespaced_custom_object(
                SVS_CRD_GROUP,
                SVS_CRD_VERSION,
                namespace.metadata.name,
                SVS_CRD_PLURAL).get('items', [])
            volume_snapshots = custom_api.list_namespaced_custom_object(
                VS_CRD_GROUP,
                VS_CRD_VERSION,
                namespace.metadata.name,
                VS_CRD_PLURAL).get('items', [])
            for scheduled_snapshot in scheduled_snapshots:
                existing_snapshots = get_associated_snapshots(scheduled_snapshot, volume_snapshots)
                if new_snapshot_needed(scheduled_snapshot, existing_snapshots):
                    create_new_snapshot(scheduled_snapshot)
                cleanup_old_snapshots(scheduled_snapshot, existing_snapshots)


if __name__ == '__main__':
    try:
        main()
    except kubernetes.client.rest.ApiException:
        logging.exception('Unhandled ApiException encountered')
