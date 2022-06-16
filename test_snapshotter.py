from datetime import datetime, timedelta, timezone
import kubernetes
import unittest
from unittest.mock import Mock, call, ANY


K8S_VERSION_INFO = kubernetes.client.VersionInfo(
    build_date='2019-08-05T09:15:22Z',
    compiler='gc',
    git_commit='f6278300bebbb750328ac16ee6dd3aa7d3549568',
    git_tree_state='clean',
    git_version='v1.15.2',
    go_version='go1.12.5',
    major='1',
    minor='15',
    platform='linux/amd64')

kubernetes.config.load_incluster_config = Mock()
kubernetes.client.VersionApi = Mock(autospec=True)
kubernetes.client.VersionApi.return_value.get_code = Mock(return_value=K8S_VERSION_INFO)
kubernetes.client.CoreV1Api = Mock(autospec=True)
kubernetes.client.CustomObjectsApi = Mock(autospec=True)

import snapshotter

ACTIVE_NAMESPACE = kubernetes.client.V1Namespace(
    metadata=kubernetes.client.V1ObjectMeta(name='activeNamespace'),
    status=kubernetes.client.V1NamespaceStatus(phase='Active'))

TERMINATING_NAMESPACE = kubernetes.client.V1Namespace(
    metadata=kubernetes.client.V1ObjectMeta(name='terminatingNamespace'),
    status=kubernetes.client.V1NamespaceStatus(phase='Terminating'))

NAMESPACES = kubernetes.client.V1NamespaceList(items=[ACTIVE_NAMESPACE, TERMINATING_NAMESPACE])
kubernetes.client.CoreV1Api.return_value.list_namespace = Mock(return_value=NAMESPACES)


class StringStartsWith(str):
    def __eq__(self, other):
        return other is not None and other.startswith(self)


class Snapshotter(unittest.TestCase):
    def setUp(self):
        kubernetes.client.CustomObjectsApi.return_value.list_namespaced_custom_object = Mock(
            side_effect=self.handle_list_namespaced_custom_object)

    def tearDown(self):
        self.scheduled_volume_snapshots = []
        self.volume_snapshots = []
        kubernetes.client.CoreV1Api.return_value.list_namespace.reset_mock()
        kubernetes.client.CustomObjectsApi.return_value.list_namespaced_custom_object.reset_mock()
        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object.reset_mock()
        kubernetes.client.CustomObjectsApi.return_value.delete_namespaced_custom_object.reset_mock()
        kubernetes.client.CustomObjectsApi.return_value.delete_namespaced_custom_object.reset_mock()

    def set_volume_snapshot_version(self, volume_snapshot_version):
        snapshotter.VS_CRD_VERSION = volume_snapshot_version

    def handle_list_namespaced_custom_object(self, group, version, namespace, plural, **kwargs):
        if plural == 'scheduledvolumesnapshots':
            return {'items': self.scheduled_volume_snapshots}
        elif plural == 'volumesnapshots':
            return {'items': self.volume_snapshots}

    def create_scheduled_volume_snapshot(self, snapshot_frequency, snapshot_retention):
        return {
            'metadata': {
                'namespace': 'activeNamespace',
                'name': 'test'
            },
            'spec': {
                'persistentVolumeClaimName': 'some-pvc',
                'snapshotFrequency': snapshot_frequency,
                'snapshotRetention': snapshot_retention,
                'snapshotClassName': 'ebs',
                'snapshotLabels': {
                    'labelOne': 'someValue'
                }
            }
        }

    def create_volume_snapshot_v1alpha1(self, created_minutes_ago):
        return {
            'metadata': {
                'creationTimestamp': (datetime.now(timezone.utc) - timedelta(minutes=created_minutes_ago)).isoformat(),
                'name': 'some-pvc-1582056377',
                'labels': {
                    'scheduled-volume-snapshot': 'test'
                }
            },
            'spec': {
                'source': {
                    'kind': 'PersistentVolumeClaim',
                    'name': 'some-pvc'
                },
                'snapshotContentName': 'content'
            },
            'status': {
                'readyToUse': True
            }
        }

    def test_new_snapshot_not_needed(self):
        self.set_volume_snapshot_version('v1alpha1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot('1h', '3h')]
        self.volume_snapshots = [self.create_volume_snapshot_v1alpha1(5)]

        snapshotter.main()

        kubernetes.client.CoreV1Api.return_value.list_namespace.assert_called()
        kubernetes.client.CustomObjectsApi.return_value.list_namespaced_custom_object.assert_has_calls([
            call(
                snapshotter.SVS_CRD_GROUP,
                snapshotter.SVS_CRD_VERSION,
                'activeNamespace',
                snapshotter.SVS_CRD_PLURAL
            ),
            call(
                snapshotter.VS_CRD_GROUP,
                snapshotter.VS_CRD_VERSION,
                'activeNamespace',
                snapshotter.VS_CRD_PLURAL
            )
        ])
        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object.assert_not_called()
        kubernetes.client.CustomObjectsApi.return_value.delete_namespaced_custom_object.assert_not_called()

    def test_new_snapshot_create_fails(self):
        self.set_volume_snapshot_version('v1alpha1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot('1h', '3h')]
        self.volume_snapshots = [self.create_volume_snapshot_v1alpha1(61)]
        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object = Mock(
            side_effect=kubernetes.client.rest.ApiException())

        snapshotter.main()

        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object.assert_called_with(
            snapshotter.VS_CRD_GROUP,
            snapshotter.VS_CRD_VERSION,
            'activeNamespace',
            snapshotter.VS_CRD_PLURAL,
            ANY
        )

    def test_new_v1alpha1_snapshot_created(self):
        self.set_volume_snapshot_version('v1alpha1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot('1h', '3h')]
        self.volume_snapshots = [self.create_volume_snapshot_v1alpha1(61)]

        snapshotter.main()

        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object.assert_called_with(
            snapshotter.VS_CRD_GROUP,
            snapshotter.VS_CRD_VERSION,
            'activeNamespace',
            snapshotter.VS_CRD_PLURAL,
            {
                'apiVersion': 'snapshot.storage.k8s.io/v1alpha1',
                'kind': 'VolumeSnapshot',
                'metadata': {
                    'name': StringStartsWith('test-'),
                    'namespace': 'activeNamespace',
                    'labels': {
                        'labelOne': 'someValue',
                        'scheduled-volume-snapshot': 'test'
                    }
                },
                'spec': {
                    'snapshotClassName': 'ebs',
                    'source': {
                        'apiGroup': None,
                        'kind': 'PersistentVolumeClaim',
                        'name': 'some-pvc'
                    }
                }
            }
        )

    def test_new_v1beta1_snapshot_created(self):
        self.set_volume_snapshot_version('v1beta1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot('5m', -1)]
        self.volume_snapshots = []

        snapshotter.main()

        kubernetes.client.CustomObjectsApi.return_value.create_namespaced_custom_object.assert_called_with(
            snapshotter.VS_CRD_GROUP,
            snapshotter.VS_CRD_VERSION,
            'activeNamespace',
            snapshotter.VS_CRD_PLURAL,
            {
                'apiVersion': 'snapshot.storage.k8s.io/v1beta1',
                'kind': 'VolumeSnapshot',
                'metadata': {
                    'name': StringStartsWith('test-'),
                    'namespace': 'activeNamespace',
                    'labels': {
                        'labelOne': 'someValue',
                        'scheduled-volume-snapshot': 'test'
                    }
                },
                'spec': {
                    'volumeSnapshotClassName': 'ebs',
                    'source': {
                        'persistentVolumeClaimName': 'some-pvc'
                    }
                }
            }
        )

    def test_delete_v1alpha1_snapshot(self):
        self.set_volume_snapshot_version('v1alpha1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot(24, 1)]
        self.volume_snapshots = [self.create_volume_snapshot_v1alpha1(120)]

        snapshotter.main()

        kubernetes.client.CustomObjectsApi.return_value.delete_namespaced_custom_object.assert_called_with(
            snapshotter.VS_CRD_GROUP,
            snapshotter.VS_CRD_VERSION,
            'activeNamespace',
            snapshotter.VS_CRD_PLURAL,
            'some-pvc-1582056377')

    def test_delete_fails_invalid_retention(self):
        self.set_volume_snapshot_version('v1alpha1')
        self.scheduled_volume_snapshots = [self.create_scheduled_volume_snapshot('abcd', 'wxyz')]
        self.volume_snapshots = [self.create_volume_snapshot_v1alpha1(120)]

        snapshotter.main()

        kubernetes.client.CustomObjectsApi.return_value.delete_namespaced_custom_object.assert_not_called()


if __name__ == '__main__':
    unittest.main()
