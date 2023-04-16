# Nautobot Jobs
A collection of Nautobot jobs to make life easier.
## Get Device OS
#### Purpose
Automatically build device <-> software relationships in Nautobot for the
Device Lifecycle app.
#### Depencies
- [Nautobot Device Lifecycle Management App](https://github.com/nautobot/nautobot-plugin-device-lifecycle-mgmt)
- [Nautobot Plugin Nornir](nautobot_plugin_nornir)
- [Nautobot Golden Config App](https://github.com/nautobot/nautobot-plugin-golden-config)
#### Job Logic
1. Use 'nornir_napalm' 'get_facts' to retrieve 'os_version'
2. Create software version based on 'os_version' in Nautobot LCM app
3. Create software to device relationship
#### Notes
- Shoutout to [dpeachey](https://github.com/dpeachey/nautobot-custom-jobs) for
the Nornir patterns. His repo has a collection of very useful Nautobot jobs.
- Once adding this to your nautobot repo, you can manually
group this job with the 'Device/Software Lifecycle Reporting'
Jobs.