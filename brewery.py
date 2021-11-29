import os
import sys
import argparse
import urllib.request
import time
import shutil
from distutils.version import StrictVersion
from copy import deepcopy
from datetime import datetime

import yaml

DC_TEMPLATE = "./templates/docker-compose-template.yml"
DC_MAIN_FILE = "docker-compose.yml"

GC_BUCKET_API_URL = "https://storage.googleapis.com/storage/v1/b/halconfig/o"
VERSIONS_URL = f"{GC_BUCKET_API_URL}/versions.yml?alt=media"
BOM_URL = f"{GC_BUCKET_API_URL}/bom%2F__VERSION__.yml?alt=media"

def info(msg):
    return f"[ INFO ] {msg}"

def warn(msg):
    return f"[ WARN ] {msg}"

def abort(msg):
    print(f"[ ABRT ] {msg}")
    sys.exit(1)

def epoch_time_to_str(timestamp):
    """ truncating last free digists, ns """
    return time.strftime(
        '%Y-%m-%d %H:%M:%S UTC',
        time.localtime(int(str(timestamp)[:-3]))
    )

def get_url_content(url):
    """ get url content or retun None in case of issues """
    res = None
    try:
        res = urllib.request.urlopen(url).read()
    except urllib.error.HTTPError as err_exc:
        print(warn(f"Failed to get {url}: {err_exc}"))
    return res

def parse_args():
    """ parse command line arguments """
    parser = argparse.ArgumentParser(
        description='Generate docker complose for running spinnaker locally'
    )
    parser.add_argument(
        '--show-available-releases',
        help='list available spinnaker releases',
        action="store_true",
        dest="available_releases"
    )
    parser.add_argument(
        '--show-latest-release',
        help='show most recent release only',
        action="store_true",
        dest="latest_release"
    )
    parser.add_argument(
        '--show-release-bom',
        help=(
            "show BOM (Bill Of Materials) for a particular release. " \
            "SPINNAKER_RELEASE env variable has to be set"
        ),
        action="store_true",
        dest="release_bom"
    )
    parser.add_argument(
        '--generate-docker-compose',
        help=(
            "generate docker-compose.yml. " \
            "SPINNAKER_RELEASE env variable has to be set"
        ),
        action="store_true",
        dest="generate_dc"
    )

    args = parser.parse_args()

    if all(not _ for _ in vars(args).values()):
        print(parser.format_help())
        sys.exit(0)

    return args

def parse_yaml(func):
    """ decorator for parsing yaml """
    def wrapper(*args, **kwargs):
        return yaml.safe_load(func(*args, **kwargs))
    return wrapper

class SpinBrewery:
    """ spinbrewery main class """
    def __init__(self):
        self.versions = self.prepare_versions()

    @parse_yaml
    def prepare_versions(self):
        """ gets info about all the releases """
        res = get_url_content(VERSIONS_URL) or abort(f"Failed to get {VERSIONS_URL}")
        return res

    @parse_yaml
    def get_bom(self, release):
        """ get BOM for particular release, in yaml """
        url = deepcopy(BOM_URL).replace("__VERSION__", release)
        res = get_url_content(url) or abort(f"Failed to get {url}")
        return res

    def load_dc_template(self, template=DC_TEMPLATE):
        with open(template, "r") as dc_template:
            return yaml.safe_load(dc_template)

    def prepare_docker_compose(self, release):
        """ prepare docker-compose.yml based on dc template """
        services = {}
        # parse dc template
        dc_tmpl_data = self.load_dc_template()
        # get bom data
        bom_data = self.get_bom(release)

        # get docker registry url from BOM
        try:
            bom_docker_registry = bom_data.get("artifactSources").get("dockerRegistry")
        except AttributeError:
            abort("Failed to get docker registry from BOM (artifactSources.dockerRegistry)")

        for service in dc_tmpl_data.get("services"):
            bom_found = False

            for sdef in bom_data.get("services"):
                if service.endswith(sdef):
                    try:
                        sdef_version = bom_data.get("services").get(sdef).get("version")
                        print(info(f"{service}: found {sdef} in BOM: {sdef_version}"))
                    except AttributeError:
                        print(warn(f"{sdef}: failed to get release version from BOM"))
                        break

                    new_sdef = deepcopy(dc_tmpl_data.get("services").get(service))
                    if not isinstance(new_sdef, dict):
                        print(warn(f"{service}: dc template is broken for service, skipping"))
                        break

                    # set image
                    new_sdef["image"] = f"{bom_docker_registry}/{sdef}:{sdef_version}"
                    services[service] = new_sdef
                    bom_found = True
                    break

            if not bom_found:
                services[service] = deepcopy(dc_tmpl_data.get("services").get(service))
                print(warn(f"{service}: no BOM record found! Using template definition"))

        if os.path.isfile(DC_MAIN_FILE):
            datestr = datetime.today().strftime('%H%M%S-%Y%m%d')
            bu_fname = f"docker-compose-bu-{datestr}.yml"
            shutil.move(DC_MAIN_FILE, bu_fname)
            print(info(f"Moved existing {DC_MAIN_FILE} to {bu_fname}"))

        dc_tmpl_data["services"] = services
        with open(DC_MAIN_FILE, 'w') as outfile:
            yaml.dump(dc_tmpl_data, outfile, default_flow_style=False)
            print(info(f"Generated {DC_MAIN_FILE}"))

    def show_latest_release(self):
        """ show metadata for most recent Spinnaker release """
        latest = self.versions.get("latestSpinnaker")

        if not latest:
            print(warn("Failed to get latest release"))
            return

        try:
            data = next(_ for _ in self.versions.get("versions") if _.get("version") == latest)
        except (KeyError, StopIteration):
            print(warn(f"Latest release is {latest}, but we failed to get metadata for it."))
            return

        SpinBrewery.print_single_version_data(data)

    def show_available_releases(self):
        """ show metadata for all available Spinnaker releases """
        versions = self.versions.get("versions")

        if not versions:
            print(warn("Failed to get availabe versions"))
            return

        sorted_versions = [_["version"] for _ in versions]
        sorted_versions.sort(key=StrictVersion)
        sorted_versions.reverse()

        for version in sorted_versions:
            SpinBrewery.print_single_version_data(
                next(_ for _ in versions if _["version"] == version)
            )

    def show_bom(self, release):
        """ show bom for particular release """
        bom_data = self.get_bom(release)
        print(yaml.dump(bom_data))

    @classmethod
    def print_single_version_data(cls, data):
        """ just a helper to show metadata for a single release """
        for count, key in enumerate(data):
            prefix = "- " if count == 0 else "  "
            if key == "lastUpdate":
                msg = f"{prefix}{key}: {epoch_time_to_str(data[key])}"
            else:
                msg = f"{prefix}{key}: {data[key]}"
            print(msg)

if __name__ == "__main__":
    ARGS = parse_args()
    SPINB = SpinBrewery()

    if ARGS.latest_release:
        print(info("Latest release metadata:"))
        SPINB.show_latest_release()

    elif ARGS.available_releases:
        print(info("Available releases:"))
        SPINB.show_available_releases()

    elif ARGS.release_bom:

        SPINNAKER_RELEASE = os.getenv("SPINNAKER_RELEASE") \
            or abort("SPINNAKER_RELEASE env variable is not set")

        print(info(f"BOM for release {SPINNAKER_RELEASE}:"))
        SPINB.show_bom(SPINNAKER_RELEASE)

    elif ARGS.generate_dc:

        SPINNAKER_RELEASE = os.getenv("SPINNAKER_RELEASE") \
            or abort("SPINNAKER_RELEASE env variable is not set")

        print(info(f"Generating docker compose for release {SPINNAKER_RELEASE}:"))
        SPINB.prepare_docker_compose(SPINNAKER_RELEASE)
