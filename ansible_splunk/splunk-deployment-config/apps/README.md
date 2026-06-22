# Splunk Apps

Place your Splunk app directories here. Each subdirectory should be a Splunk app.

Example layout:

```
apps/
├── your_app_name/
│   ├── default/
│   └── metadata/
└── another_app/
```

The Apps Manager in splunk-ansible-ui lists directories under this folder. Deploy playbooks copy selected apps to Splunk targets defined in `inventory/group_vars/`.
