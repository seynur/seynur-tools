IN=<IN>
OUT=<OUT>

awk '
function reset_flags() {
  has_corr=0
  has_notable1=0

  has_rule_title=0
  has_label=0
  has_desc=0          # action.notable.param.rule_description
  has_invest=0
  has_risk=0
  has_plain_desc=0    # description

  # Values for alert description composition
  plain_desc_val=""
  label_val=""
  rule_desc_val=""
  next_steps_val=""
  annotations_val=""

  stanza_name=""
  pos_header=0
}

function print_raw_stanza(  i) {
  for (i=1; i<=n; i++) print lines[i]
  print ""
}

function is_empty_value(l,   tmp) {
  tmp=l
  sub(/^[^=]+=[[:space:]]*/, "", tmp)
  return (tmp ~ /^[[:space:]]*$/)
}

function is_value_one(l,   tmp) {
  tmp=l
  sub(/^[^=]+=[[:space:]]*/, "", tmp)
  gsub(/[[:space:]]+$/, "", tmp)
  return (tmp == "1")
}

function extract_value(line,   v) {
  v=line
  sub(/^[^=]+=[[:space:]]*/, "", v)
  gsub(/[[:space:]]+$/, "", v)
  # Escape double quotes so we can wrap the whole description in quotes
  gsub(/"/, "\\\"", v)
  return v
}

function build_alert_description(   s, base) {
  s=""

  # description: <description> OR <label>
  base=""
  if (plain_desc_val != "") base = plain_desc_val
  else if (label_val != "") base = label_val
  else if (rule_desc_val != "") base = rule_desc_val

  if (base != "") s = base

  # Absolute fallback if everything is empty
  if (s == "") s = stanza_name

  return s
}

# Correlation search but NOT notable-producing: convert to normal alert stanza
function output_as_alert(   i, alert_desc) {

  alert_desc = build_alert_description()

  for (i=1; i<=n; i++) {

    # Drop ES correlation/notable/risk related keys when converting to alert
    if (lines[i] ~ /^[[:space:]]*action\.correlationsearch(\.|[[:space:]]*=)/) continue
    if (lines[i] ~ /^[[:space:]]*action\.notable(\.|[[:space:]]*=)/) continue
    if (lines[i] ~ /^[[:space:]]*action\.risk(\.|[[:space:]]*=)/) continue

    # Drop any existing plain description so we can replace it
    if (lines[i] ~ /^[[:space:]]*description[[:space:]]*=/) continue

    print lines[i]

    # Inject the composed description right after stanza header
    if (i == pos_header) {
      print "description = " alert_desc
    }
  }

  print ""
}

function flush_stanza(   i, pos_inject, meaningful) {

  if (n==0) return

  # Non-correlation stanzas: copy as-is
  if (!has_corr) {
    print_raw_stanza()
    delete lines; n=0
    reset_flags()
    return
  }

  # Correlation stanza but no header name: copy as-is
  if (stanza_name == "") {
    print_raw_stanza()
    delete lines; n=0
    reset_flags()
    return
  }

  # Keep your meaningful rule (skip correlation stanzas that are only header + title)
  meaningful = 0
  for (i=1; i<=n; i++) {
    if (lines[i] !~ /^\[/ &&
        lines[i] !~ /^[[:space:]]*$/ &&
        lines[i] !~ /^[[:space:]]*action\.notable\.param\.rule_title[[:space:]]*=/) {
      meaningful = 1
      break
    }
  }

  if (!meaningful) {
    delete lines; n=0
    reset_flags()
    return
  }

  # If correlation search does NOT produce notables => convert to alert and stop
  if (!has_notable1) {
    output_as_alert()
    delete lines; n=0
    reset_flags()
    return
  }

  # --- Notable-producing correlation search path (YOUR EXISTING LOGIC) ---

  # Inject after rule_title if present, else after label, else after header
  pos_inject = 0
  for (i=1; i<=n; i++) {
    if (lines[i] ~ /^[[:space:]]*action\.notable\.param\.rule_title[[:space:]]*=/) { pos_inject=i; break }
  }
  if (pos_inject == 0) {
    for (i=1; i<=n; i++) {
      if (lines[i] ~ /^[[:space:]]*action\.correlationsearch\.label[[:space:]]*=/) { pos_inject=i; break }
    }
  }
  if (pos_inject == 0) pos_inject = pos_header

  for (i=1; i<=n; i++) {

    # Overwrite plain "description" if it exists but empty
    if (lines[i] ~ /^[[:space:]]*description[[:space:]]*=/) {
      if (is_empty_value(lines[i])) {
        lines[i] = "description = Generic Desc - " stanza_name
      }
      has_plain_desc=1
    }

    # Overwrite notable rule_title if it exists but empty
    if (lines[i] ~ /^[[:space:]]*action\.notable\.param\.rule_title[[:space:]]*=/) {
      if (is_empty_value(lines[i])) {
        lines[i] = "action.notable.param.rule_title = Generic Rule Title - " stanza_name
      }
      has_rule_title=1
    }

    # Overwrite notable rule_description if it exists but empty
    if (lines[i] ~ /^[[:space:]]*action\.notable\.param\.rule_description[[:space:]]*=/) {
      if (is_empty_value(lines[i])) {
        lines[i] = "action.notable.param.rule_description = Generic Rule Desc - " stanza_name
      }
      has_desc=1
    }

    # Overwrite risk message if it exists but empty
    if (lines[i] ~ /^[[:space:]]*action\.risk\.param\._risk_message[[:space:]]*=/) {
      if (is_empty_value(lines[i])) {
        lines[i] = "action.risk.param._risk_message = Generic Risk Msg - " stanza_name
      }
      has_risk=1
    }

    print lines[i]

    # Inject plain description immediately after stanza header
    if (i == pos_header) {
      if (!has_plain_desc)
        print "description = Generic Desc - " stanza_name
    }

    # Inject other missing parameters after title/label/header (pos_inject)
    if (i == pos_inject) {

      if (!has_desc)
        print "action.notable.param.rule_description = Generic Rule Desc - " stanza_name

      if (!has_rule_title)
        print "action.notable.param.rule_title = Generic Rule Title - " stanza_name

      if (!has_invest)
        print "action.notable.param.investigation_type = default"

      if (!has_risk)
        print "action.risk.param._risk_message = Generic Risk Msg - " stanza_name
    }
  }

  print ""

  delete lines; n=0
  reset_flags()
}

BEGIN { n=0; reset_flags() }

/^[[:space:]]*$/ { flush_stanza(); next }

{
  line=$0
  n++
  lines[n]=line

  # Capture stanza header and name, and remember its position
  if (line ~ /^[[:space:]]*\[[^]]+\][[:space:]]*$/) {
    pos_header = n
    stanza_name = line
    sub(/^[[:space:]]*\[/, "", stanza_name)
    sub(/\][[:space:]]*$/, "", stanza_name)
  }

  # Detect correlation search stanzas
  if (line ~ /action\.correlationsearch/) has_corr=1

  # Detect notable-producing correlations: action.notable = 1
  if (line ~ /^[[:space:]]*action\.notable[[:space:]]*=/) {
    if (is_value_one(line)) has_notable1=1
  }

  # Capture values used for ALERT description composition
  if (line ~ /^[[:space:]]*description[[:space:]]*=/) {
    has_plain_desc=1
    plain_desc_val = extract_value(line)
  }

  if (line ~ /^[[:space:]]*action\.correlationsearch\.label[[:space:]]*=/) {
    has_label=1
    label_val = extract_value(line)
  }

  if (line ~ /^[[:space:]]*action\.notable\.param\.rule_description[[:space:]]*=/) {
    has_desc=1
    rule_desc_val = extract_value(line)
  }

  if (line ~ /^[[:space:]]*action\.notable\.param\.next_steps[[:space:]]*=/) {
    next_steps_val = extract_value(line)
  }

  if (line ~ /^[[:space:]]*action\.correlationsearch\.annotations[[:space:]]*=/) {
    annotations_val = extract_value(line)
  }

  # Track notable fields for NOTABLE-producing path
  if (line ~ /^[[:space:]]*action\.notable\.param\.rule_title[[:space:]]*=/) has_rule_title=1
  if (line ~ /^[[:space:]]*action\.notable\.param\.investigation_type[[:space:]]*=/) has_invest=1
  if (line ~ /^[[:space:]]*action\.risk\.param\._risk_message[[:space:]]*=/) has_risk=1
}

END { flush_stanza() }
' "$IN" > "$OUT"