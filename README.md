[![CI](https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/workflows/CI/badge.svg)](https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/actions?query=workflow%3ACI)

# Kubernetes Scheduled Volume Snapshotter

## Overview
This repository builds upon the [Kubernetes CSI's](https://kubernetes-csi.github.io/docs/introduction.html) `VolumeSnapshot` custom resource by allowing users to automatically snapshot their persistent volumes on a schedule they define. The functionality provided by this tool is something the [Kubernetes Storage Special Interest Group](https://github.com/kubernetes/community/tree/master/sig-storage) has on their [roadmap](https://github.com/kubernetes-incubator/external-storage/blob/master/snapshot/doc/volume-snapshotting-proposal.md#future-features), but has yet to be implemented.

## Prerequisites
You will need to have the `VolumeSnapshot` custom resource definition installed along with one or more [CSI drivers](https://kubernetes-csi.github.io/docs/drivers.html). For more information about VolumeSnapshots in Kubernetes and the Kubernetes Container Storage Interface, see [here](https://kubernetes.io/blog/2019/01/15/container-storage-interface-ga/).

The Scheduled Volume Snapshotter works with `v1alpha1` (Kubernetes 1.12 - 1.16), `v1beta1` (Kubernetes 1.17 - 1.19), and `v1` (Kubernetes >= 1.20) versions of the `VolumeSnapshot` custom resource.

As of version `v0.16.0`, Docker images published are compatible with both amd64 and arm64 architectures.

## Installation
The easiest way to deploy this operator is using the provided [Helm chart](./helm/charts/scheduled-volume-snapshotter):

```
helm repo add scheduled-volume-snapshotter https://raw.githubusercontent.com/ryaneorth/k8s-scheduled-volume-snapshotter/main/repo
helm upgrade --install scheduled-volume-snapshotter scheduled-volume-snapshotter/scheduled-volume-snapshotter
```

## Scheduling snapshots
Once the Helm chart is installed, you can schedule snapshots of existing persistent volumes by creating a `ScheduledVolumeSnapshot` custom resource. Here is an example:

```
apiVersion: k8s.ryanorth.io/v1beta1
kind: ScheduledVolumeSnapshot
metadata:
  name: my-scheduled-snapshot
  namespace: foo
spec:
  snapshotClassName: ebs
  persistentVolumeClaimName: some-existing-pvc
  snapshotFrequency: 1
  snapshotRetention: 3
  snapshotLabels:
    firstLabel: someLabelValue
    secondLabel: anotherLabelValue
```

See the `ScheduledVolumeSnapshot` [custom resource definition](./helm/charts/scheduled-volume-snapshotter/crds/scheduled-volume-snapshot-crd.yaml) for further details.
