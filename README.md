# spin-brewery

## Description
This project prepares docker-compose scenario for [Spinnaker](https://spinnaker.io/docs/), only for testing/demo/educational purposes. 

`Spinnaker` is a [collection of microservices](https://spinnaker.io/docs/reference/architecture/microservices-overview/), and each major Spinnaker release consists of set of releases of underlying services. Versions of underlying microservices are defined in [BOM (Bill of Materials)](https://spinnaker.io/docs/guides/operator/custom-boms/#the-bill-of-materials-bom) for each major release.

There are similar projects on github, and partially this project is based on them:

https://github.com/songrgg/spinnaker-compose

https://github.com/hbstarjason/spinnaker-local

https://github.com/whatisdot/spinnaker-compose

But `spin-brewery`, unlike the mentioned above tools, is not hardcoding any release versions in docker-compose file. Instead it dynamically generates the docker-compose scenario based on BOM, prepared by `Spinnaker` team, and you are the one to decide which major `Spinnaker` release you would like to deploy.

*NOTICE1*: `Spinnaker` has it's own installation tool, called [Halyard](https://spinnaker.io/docs/setup/install/halyard/), but it does not support installation of Spinnaker using bare `docker` or `docker-compose`.

*NOTICE2*: It is possible to setup `Spinnaker` on local Debian (**only**) machine/VM, using `Halyard`, but as of now (fall 2021) `Spinnaker` apt repo [is broken](https://github.com/spinnaker/spinnaker/issues/6488).

*NOTICE3*: service configs inside `spin-brewery` repository are optimized for Spinnaker major release **1.26.6**. Configs might need modifications for upcoming releases, and for sure need some changes in case you'd like to run some old Spinnaker version. For configs, compatible with older versions, you might want to take a look into mentioned above repos.

## Usage
### Initial preparations
ideally you shoul have custom python virtual environment, even though `spin-brewery` depends only on single library: **pyyaml**

### Prepare docker compose scenario
Get the latest release information:
```
$ python brewery.py --show-latest-release
[ INFO ] Latest release metadata:
- version: 1.26.6
  alias: Disenchantment
  changelog: https://gist.github.com/spinnaker-release/e3714a97bbdd3e7c3b4d92adec938e7f
  minimumHalyardVersion: 1.41
  lastUpdate: 2021-07-01 02:49:04 UTC
```
*OPTIONAL*: in case you want to check all the available releases:
```
$ python brewery.py --show-available-releases
[ INFO ] Available releases:
- version: 1.26.6
  alias: Disenchantment
  changelog: https://gist.github.com/spinnaker-release/e3714a97bbdd3e7c3b4d92adec938e7f
  minimumHalyardVersion: 1.41
  lastUpdate: 2021-07-01 02:49:04 UTC
...
- version: 1.19.14
  alias: Gilmore Girls A Year in the Life
  changelog: https://gist.github.com/spinnaker-release/cc4410d674679c5765246a40f28e3cad
  minimumHalyardVersion: 1.32
  lastUpdate: 2020-08-14 01:44:46 UTC
```
Export desired release version as environment variable:
```
$ export SPINNAKER_RELEASE=1.26.6
```
*OPTIONAL*: you might want to see BOM for desired release:
```
$ python brewery.py --show-release-bom
[ INFO ] BOM for release 1.26.6:
artifactSources:
  debianRepository: https://dl.bintray.com/spinnaker-releases/debians
  dockerRegistry: us-docker.pkg.dev/spinnaker-community/docker
  gitPrefix: https://github.com/spinnaker
  googleImageProject: marketplace-spinnaker-release
dependencies:
  consul:
    version: 0.7.5
  redis:
    version: 2:2.8.4-2
  vault:
    version: 0.7.0
services:
  clouddriver:
    commit: 4801f1b941d0fab498d58c6076b6ec28bb1a8aaa
    version: 8.0.4-20210625060028
  deck:
    commit: ef229a1b4c8e244daa5633716f2c90919f2eda1b
    version: 3.7.2-20210614020020
...
  rosco:
    commit: 0dd3f3988cb134581edca4aaff74fe34b4f518d8
    version: 0.25.0-20210422230020
timestamp: '2021-06-30 06:23:13'
version: 1.26.6
```
Generate docker compose scenario. File docker-compose.yml will be generated in the root of the repo. In case some older scenario exists - it will me moved to backups file:
```
$ python brewery.py --generate-docker-compose
[ INFO ] Generating docker compose for release 1.26.6:
[ INFO ] spin-clouddriver: found clouddriver in BOM: 8.0.4-20210625060028
[ INFO ] spin-deck: found deck in BOM: 3.7.2-20210614020020
[ INFO ] spin-echo: found echo in BOM: 2.17.1-20210429125836
[ INFO ] spin-front50: found front50 in BOM: 0.27.1-20210625161956
[ INFO ] spin-gate: found gate in BOM: 1.22.1-20210603020019
[ INFO ] spin-igor: found igor in BOM: 1.16.0-20210422230020
[ INFO ] spin-orca: found orca in BOM: 2.20.3-20210630022216
[ INFO ] spin-rosco: found rosco in BOM: 0.25.0-20210422230020
[ INFO ] spin-fiat: found fiat in BOM: 1.16.0-20210422230020
[ WARN ] spin-redis: no BOM record found! Using template definition
[ WARN ] spin-db: no BOM record found! Using template definition
[ INFO ] Moved existing docker-compose.yml to docker-compose-bu-185814-20211129.yml
[ INFO ] Generated docker-compose.yml
```
### Deploy docker compose scenario
*IMPORTANT*: keep in mind that 4core/16RAM is recommended to deploy all the services. In my case I was running setup on 8core/16RAM, without any significant issues.

First of all - deploy MySQL DB machine:
```
$ docker-compose up -d spin-db
```
Now add needed database/permissions:
```
$ docker exec -it spin-brewery_spin-db_1 sh -c 'exec mysql -uroot -pspinnaker < /opt/spinnaker/sql/front50_mysql.sql'
```
*OPTIONAL*: bring Front50 servive, to ensure MySQL is ok, and service is able to prepare all the needed tables.
```
$ docker-compose up -d spin-db
$ docker logs spin-brewery_spin-front50_1 -f
```
Bring up all the services:
```
$ docker-compose up -d
```
Visit `http://localhost:9000` to access `Deck` UI.
*NOTICE*: as of now, docker compose scenario is not configured to perform extensive checkouts, so connectivity to underlying services might not be in place immediately, since Java services might need time to start up (main `Deck` dependency is `Gate` - a gateway to underlying microservices).
