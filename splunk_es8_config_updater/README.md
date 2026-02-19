# splunk_es8_config_updater

This script updates Splunk correlation search stanzas (typically from `savedsearches.conf`) so they are compatible with Splunk Enterprise Security 8.x detection rule requirements.

It is intended to help with ES upgrades from 7.x to 8.x by filling fields that were optional before but are now required or expected.

Reference blog post:
`https://blog.seynur.com/splunk/2026/02/18/upgrading-es-from-es7x-to-es811.html`

## What the script does

For correlation search stanzas (`action.correlationsearch`):

- Adds `description` if missing.
- Adds `action.notable.param.rule_description` if missing.
- Adds `action.notable.param.investigation_type = default` if missing.
- Adds `action.risk.param._risk_message` if missing.
- Adds `action.risk.param.rule_title` if missing.
- Replaces empty values for the fields above with generic values.

Other stanzas are copied as-is.

## Usage

The script takes input/output paths from environment variables:

```bash
IN=<input-path> OUT=<output-path> bash splunk_es8_config_updater.sh
```

Example:

```bash
IN=/opt/splunk/etc/apps/SplunkEnterpriseSecuritySuite/local/savedsearches.conf \
OUT=/tmp/merged_savedsearches.conf \
bash splunk_es8_config_updater.sh
```

OR 

if you fill `IN` ad `OUT` parameters in the script, you can use:

```bash
splunk_es8_config_updater.sh
```

## Notes

- Input should be a Splunk `.conf` file containing saved search stanzas.
- The script writes a transformed file to `OUT`; it does not edit the source file in place.
- Generic values are based on stanza name and are meant as migration placeholders.
