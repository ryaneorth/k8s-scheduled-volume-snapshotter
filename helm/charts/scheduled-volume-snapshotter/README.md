# Helm Chart
Using this Helm chart is the easiest way to install the scheduled volume snapshotter. To install with the base configuration, execute the following command:

```
helm upgrade --install scheduled-volume-snapshotter \
	https://github.com/ryaneorth/scheduled-volume-snapshotter/releases/download/v0.5.1/helm-chart.tgz
```


Values which can be overridden are documented below.

| Parameter              | Description                                                              | Default                                  |
| ---------------------- | ------------------------------------------------------------------------ | ---------------------------------------- |
| `image.repository`     | The image to be used for the CronJob                                     | `ryaneorth/scheduled-volume-snapshotter` |
| `image.pullPolicy`     | The pull policy for the CronJob pods                                     | `IfNotPresent`                           |
| `schedule`             | The cron expression for how often the job should execute                 | `*/15 * * * *`                           |
| `rbac.enabled`         | Flag indicating whether the rbac resources should be installed           | `true`                                   |
| `logLevel`             | The Python log level for the jobs                                        | `INFO`                                   |
