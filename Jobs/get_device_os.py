# type: ignore
"""Use retrieve device OS version and document in Nautobot LCM app."""

from django.contrib.contenttypes.models import ContentType

from nautobot.tenancy.models import Tenant, TenantGroup
from nautobot.extras.jobs import Job, MultiObjectVar
from nautobot.extras.models import Tag, Relationship, RelationshipAssociation
from nautobot.dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Manufacturer,
    Platform,
    Region,
    Site,
)

from nautobot_golden_config.utilities.helper import get_job_filter

from nautobot_device_lifecycle_mgmt.models import SoftwareLCM

from nautobot_plugin_nornir.constants import NORNIR_SETTINGS
from nautobot_plugin_nornir.plugins.inventory.nautobot_orm import NautobotORMInventory

from nornir import InitNornir
from nornir.core.plugins.inventory import InventoryPluginRegister
from nornir.core.task import Result, Task

from nornir_napalm.plugins.tasks import napalm_get

InventoryPluginRegister.register("nautobot-inventory", NautobotORMInventory)


def init_nornir(data) -> InitNornir:
    """Initialise Nornir object."""
    return InitNornir(
        runner=NORNIR_SETTINGS.get("runner"),
        logging={"enabled": False},
        inventory={
            "plugin": "nautobot-inventory",
            "options": {
                "credentials_class": NORNIR_SETTINGS.get("credentials"),
                "params": NORNIR_SETTINGS.get("inventory_params"),
                "queryset": get_job_filter(data),
            },
        },
    )


class CreateSoftwareRel(Job):
    """Retrieve os_version and build Software to Device relationship."""

    class Meta:
        """Job attributes."""

        name = "Get Device OS Version"
        description = "Get OS version, build device to software relationship"
        read_only = False
        approval_required = False
        has_sensitive_variables = False

    # Form fields
    tenant_group = MultiObjectVar(model=TenantGroup, required=False)
    tenant = MultiObjectVar(model=Tenant, required=False)
    region = MultiObjectVar(model=Region, required=False)
    site = MultiObjectVar(model=Site, required=False)
    role = MultiObjectVar(model=DeviceRole, required=False)
    manufacturer = MultiObjectVar(model=Manufacturer, required=False)
    platform = MultiObjectVar(model=Platform, required=False)
    device_type = MultiObjectVar(model=DeviceType, required=False)
    device = MultiObjectVar(model=Device, required=False)
    tag = MultiObjectVar(model=Tag, required=False)

    def run(self, data, commit) -> None:
        """Run get os version job."""
        # Init Nornir and run configure device task for each device
        try:
            with init_nornir(data) as nornir_obj:
                nr = nornir_obj
                nr.run(
                    task=self._get_os_version,
                    name=self.name,
                )
        except Exception as err:
            self.log_failure(None, f"```\n{err}\n```")
            raise

    def _get_os_version(self, task: Task) -> Result:
        """Get_facts, update OS Version in Nautobot."""
        # Get device object
        device_obj = task.host.data["obj"]

        # Run NAPALM task to retrieve os_version
        try:
            facts = task.run(task=napalm_get, getters="get_facts")
        except Exception as err:
            self.log_failure(
                obj=device_obj, message=f"FAILED:\n```\n{err.result.exception}\n```"
            )
            raise

        get_facts_version = facts.result["get_facts"]["os_version"]
        software_rel_id = Relationship.objects.get(name="Software on Device").id

        # Check if software exists in nautobot database. If not, create it.
        if SoftwareLCM.objects.filter(version=get_facts_version).exists():
            software = SoftwareLCM.objects.get(version=get_facts_version)
        else:
            platform = device_obj.platform
            software = SoftwareLCM(version=get_facts_version, device_platform=platform)
            software.validated_save()
            self.log_info(
                obj=software, message=f"Created software version {software.version}"
            )

        # Check if software to dev relationship already exists. If not, create it.
        if RelationshipAssociation.objects.filter(
            relationship=software_rel_id,
            source_id=software.id,
            destination_id=device_obj.id,
        ).exists():
            self.log_info(
                obj=device_obj,
                message=f"Relationship {device_obj.name} <-> {software} exists.",
            )
        else:
            rel_type = Relationship.objects.get(name="Software on Device")
            source_ct = ContentType.objects.get(model="softwarelcm")
            dest_ct = ContentType.objects.get(model="device")
            created_rel = RelationshipAssociation(
                relationship=rel_type,
                source_type=source_ct,
                source=software,
                destination_type=dest_ct,
                destination=device_obj,
            )
            created_rel.validated_save()
            self.log_success(
                obj=device_obj,
                message=f"Created {device_obj.name} <-> {software} relationship.",
            )
