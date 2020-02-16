from datetime import datetime, timedelta, timezone
import dateutil.parser
import kubernetes
import logging
import time
import os

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
kubernetes.config.load_incluster_config()
K8S_VERSION_INFO = kubernetes.client.VersionApi().get_code()

SVS_CRD_GROUP = 'k8s.ryanorth.io'
SVS_CRD_VERSION = 'v1beta1'
SVS_CRD_PLURAL = 'scheduledvolumesnapshots'
VS_CRD_GROUP = 'snapshot.storage.k8s.io'
VS_CRD_VERSION = 'v1alpha1' if int(K8S_VERSION_INFO.major) == 1 and int(
    K8S_VERSION_INFO.minor) < 17 else 'v1beta1'
VS_CRD_PLURAL = 'volumesnapshots'
VS_CRD_KIND = 'VolumeSnapshot'
VSC_CRD_GROUP = 'snapshot.storage.k8s.io'
VSC_CRD_VERSION = 'v1alpha1' if int(K8S_VERSION_INFO.major) == 1 and int(
    K8S_VERSION_INFO.minor) < 17 else 'v1beta1'
VSC_CRD_PLURAL = 'volumesnapshotcontents'

v1 = kubernetes.client.CoreV1Api()
custom_api = kubernetes.client.CustomObjectsApi()


def get_existing_snapshots(scheduled_snapshot):
    scheduled_snapshot_pvc = scheduled_snapshot.get(
        'spec', {}).get('persistentVolumeClaimName')
    try:
        all_volume_snapshots = custom_api.list_namespaced_custom_object(
            VS_CRD_GROUP,
            VS_CRD_VERSION,
            scheduled_snapshot.get('metadata', {}).get('namespace'),
            VS_CRD_PLURAL).get('items', [])
    except kubernetes.client.rest.ApiException as e:
        all_volume_snapshots = []
        logging.exception('Unable to fetch existing volume snapshots')
    if VS_CRD_VERSION == 'v1alpha1':
        filtered_snapshots = list(filter(lambda s: s.get('spec', {}).get('source', {}).get('name') == scheduled_snapshot_pvc and s.get(
            'spec', {}).get('source', {}).get('kind') == 'PersistentVolumeClaim', all_volume_snapshots))
    else:
        filtered_snapshots = list(filter(lambda s: s.get('spec', {}).get('source', {}).get(
            'persistentVolumeClaimName') == scheduled_snapshot_pvc, all_volume_snapshots))

    filtered_snapshots.sort(key=lambda s: dateutil.parser.parse(
        s.get('metadata', {}).get('creationTimestamp')))
    return filtered_snapshots


def new_snapshot_needed(scheduled_snapshot, existing_snapshots):
    time_delta = timedelta(hours=scheduled_snapshot.get(
        'spec', {}).get('snapshotFrequency'))
    return len(existing_snapshots) == 0 or datetime.now(timezone.utc) >= dateutil.parser.parse(existing_snapshots[-1].get('metadata', {}).get('creationTimestamp')) + time_delta


def create_new_snapshot(scheduled_snapshot):
    new_snapshot_name = f"{scheduled_snapshot.get('spec', {}).get('persistentVolumeClaimName')}-{str(int(time.time()))}"
    new_snapshot_namespace = scheduled_snapshot.get(
        'metadata', {}).get('namespace')
    new_snapshot_labels = scheduled_snapshot.get(
        'spec', {}).get('snapshotLabels', {})
    logging.info(
        f'Creating snapshot {new_snapshot_name} in namespace {new_snapshot_namespace}')
    volume_snapshot_content = {
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
        volume_snapshot_content['spec']['source'] = {
            'apiGroup': None,
            'kind': 'PersistentVolumeClaim',
            'name': scheduled_snapshot.get('spec', {}).get('persistentVolumeClaimName')
        }
    else:
        volume_snapshot_content['spec']['source'] = {
            'persistentVolumeClaimName': scheduled_snapshot.get('spec', {}).get('persistentVolumeClaimName')
        }
    try:
        custom_api.create_namespaced_custom_object(
            VS_CRD_GROUP,
            VS_CRD_VERSION,
            scheduled_snapshot.get('metadata', {}).get('namespace'),
            VS_CRD_PLURAL,
            volume_snapshot_content)
    except kubernetes.client.rest.ApiException as e:
        logging.exception(
            f'Unable to create volume snapshot {new_snapshot_name} in namespace {new_snapshot_namespace}')


def cleanup_old_snapshots(scheduled_snapshot, existing_snapshots):
    snapshotRetention = scheduled_snapshot.get(
        'spec', {}).get('snapshotRetention', -1)
    if snapshotRetention > 0:
        oldest_retention_time = datetime.now(
            timezone.utc) - timedelta(hours=snapshotRetention)
        for existing_snapshot in existing_snapshots:
            if dateutil.parser.parse(existing_snapshot.get('metadata', {}).get('creationTimestamp')) < oldest_retention_time:
                snapshot_namespace = scheduled_snapshot.get(
                    'metadata', {}).get('namespace')
                snapshot_name = existing_snapshot.get(
                    'metadata', {}).get('name')
                if VS_CRD_VERSION == 'v1alpha1':
                    snapshot_content_name = existing_snapshot.get(
                        'spec', {}).get('snapshotContentName')
                else:
                    snapshot_content_name = existing_snapshot.get(
                        'status', {}).get('boundVolumeSnapshotContentName')
                logging.info(
                    f'Deleting snapshot {snapshot_name} from namespace {snapshot_namespace}')
                try:
                    if snapshot_content_name:
                        # delete the associated VolumeSnapshotContent object
                        custom_api.delete_cluster_custom_object(
                            VSC_CRD_GROUP,
                            VSC_CRD_VERSION,
                            VSC_CRD_PLURAL,
                            snapshot_content_name,
                            {})
                    # delete the VolumeSnapshot object
                    custom_api.delete_namespaced_custom_object(
                        VS_CRD_GROUP,
                        VS_CRD_VERSION,
                        snapshot_namespace,
                        VS_CRD_PLURAL,
                        snapshot_name,
                        {})
                except kubernetes.client.rest.ApiException as e:
                    logging.exception(
                        f'Unable to delete volume snapshot {snapshot_name} in namespace {snapshot_namespace}')


def main():
    for namespace in v1.list_namespace().items:
        if namespace.status.phase == 'Active':
            scheduled_snapshots = custom_api.list_namespaced_custom_object(
                SVS_CRD_GROUP, SVS_CRD_VERSION, namespace.metadata.name, SVS_CRD_PLURAL).get('items', [])
            for scheduled_snapshot in scheduled_snapshots:
                existing_snapshots = get_existing_snapshots(scheduled_snapshot)
                if new_snapshot_needed(scheduled_snapshot, existing_snapshots):
                    create_new_snapshot(scheduled_snapshot)
                cleanup_old_snapshots(scheduled_snapshot, existing_snapshots)


if __name__ == '__main__':
    try:
        main()
    except kubernetes.client.rest.ApiException as e:
        logging.exception('Unhandled ApiException encountered')
