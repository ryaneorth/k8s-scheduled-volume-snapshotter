[![CI](https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/workflows/CI/badge.svg?branch=main)](https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/actions?query=workflow%3ACI)

# Kubernetes Scheduled Volume Snapshotter

## Overview
This repository builds upon the [Kubernetes CSI's](https://kubernetes-csi.github.io/docs/introduction.html) `VolumeSnapshot` custom resource by allowing users to automatically snapshot their persistent volumes on a schedule they define. The functionality provided by this tool is something the [Kubernetes Storage Special Interest Group](https://github.com/kubernetes/community/tree/master/sig-storage) has on their [roadmap](https://github.com/kubernetes-incubator/external-storage/blob/master/snapshot/doc/volume-snapshotting-proposal.md#future-features), but has yet to be implemented.

## Prerequisites
You will need to have the `VolumeSnapshot` custom resource definition installed along with one or more [CSI drivers](https://kubernetes-csi.github.io/docs/drivers.html). For more information about VolumeSnapshots in Kubernetes and the Kubernetes Container Storage Interface, see [here](https://kubernetes.io/blog/2019/01/15/container-storage-interface-ga/).

The Scheduled Volume Snapshotter works with both `v1alpha1` (Kubernetes versions 1.12 - 1.16) and `v1beta1` (Kubernetes versions >= 1.17) versions of the `VolumeSnapshot` custom resource.

## Installation
The easiest way to deploy this operator is using the provided [Helm chart](./helm/charts/scheduled-volume-snapshotter):

```
helm upgrade --install scheduled-volume-snapshotter \
	https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/releases/download/v0.10.2/helm-chart.tgz
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
