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

## Bonus
Also, you can use the commands below to sum up all `etc/*/local/savedsearches.conf` files into one.

1. To create the file that contains all searches without `savedsearches.conf` paths.

`command`:
```
find $SPLUNK_HOME/etc -path "*/local/savedsearches.conf" -type f -exec cat {} \; > /tmp/merged_savedsearches.conf

```

`output`:
```
[Threat - Oyku-ES Upgrade Test - Rule]
action.correlationsearch.enabled = 1
action.correlationsearch.label = Threat - Oyku-ES Upgrade Test - Rule
...

[Threat - Oyku-ES Upgrade Test 2 - Rule]
action.correlationsearch.enabled = 1
action.correlationsearch.label = Threat - Oyku-ES Upgrade Test 2 - Rule
...
```


2. To create the file that contains all searches with `savedsearches.conf` paths.

`command`:
```
find $SPLUNK_HOME/etc -path "*/local/savedsearches.conf" -type f -exec sh -c '
echo "### FILE: $1"
cat "$1"
echo ""
' _ {} \; > /tmp/merged_savedsearches.conf

```

`output`:
```
### FILE: /opt/splunk/etc/apps/SplunkEnterpriseSecuritySuite/local/savedsearches.conf
[Threat - Oyku-ES Upgrade Test - Rule]
action.correlationsearch.enabled = 1
action.correlationsearch.label = Threat - Oyku-ES Upgrade Test - Rule
...

### FILE: /opt/splunk/etc/apps/custom_usecase_app/local/savedsearches.conf
[Threat - Oyku-ES Upgrade Test 2 - Rule]
action.correlationsearch.enabled = 1
action.correlationsearch.label = Threat - Oyku-ES Upgrade Test 2 - Rule
...
```
