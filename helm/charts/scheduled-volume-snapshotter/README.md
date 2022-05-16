# scheduled-volume-snapshotter

Using this Helm chart is the easiest way to install the scheduled volume snapshotter. To install with the base configuration, execute the following command:

```
helm upgrade --install scheduled-volume-snapshotter \
	https://github.com/ryaneorth/k8s-scheduled-volume-snapshotter/releases/download/v0.10.1/helm-chart.tgz
```


| Parameter                     | Description                                                                                            | Default                                  |
| ----------------------------- | -------------------------------------------------------------------------------------------------------| ---------------------------------------- |
| `image.repository`            | The image to be used for the CronJob                                                                   | `ryaneorth/scheduled-volume-snapshotter` |
| `image.tag`                   | The image version to be used for the CronJob. <br> If not specified the Chart App Version will be used | `.Chart.AppVersion`                      |
| `image.pullPolicy`            | The pull policy for the CronJob pods                                                                   | `IfNotPresent`                           |
| `schedule`                    | The cron expression for how often the job should execute                                               | `*/15 * * * *`                           |
| `successfulJobsHistoryLimit`  | The number of successful jobs to retain                                                                | `3`                                      |
| `failedJobsHistoryLimit`      | The number of failed jobs to retain                                                                    | `1`                                      |
| `rbac.enabled`                | Flag indicating whether the rbac resources should be installed                                         | `true`                                   |
| `logLevel`                    | The Python log level for the jobs                                                                      | `INFO`                                   |
| `podAnnotations`              | Annotations to be added to pods                                                                        | `{}`                                     |
| `snapshotClasses`             | Optional list of VolumeSnapshotClass resources                                                         | `[]`                                     |
| `snapshots`                   | Optional list of ScheduledVolumeSnapshot resources                                                     | `[]`                                     |
| `podSecurityContext`           | The securityContext to apply to the Cronjob pods                                                       | `{}`                                     |
| `containerSecurityContext`    | The securityContext to apply to the Cronjob pods' container                                            | `{}`                                     |
| `imagePullSecrets`            | The imagePullSecrets to apply to the Cronjob pods                                                      | `[]`                                     |
