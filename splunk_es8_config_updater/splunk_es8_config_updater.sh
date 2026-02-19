IN=<input-path>
OUT=<output-path>

awk '
function reset_flags() {
  has_corr=0
  has_rule_title=0
  has_label=0
  has_desc=0          # action.notable.param.rule_description
  has_invest=0
  has_risk=0
  has_plain_desc=0    # description
  title_val=""
  label_val=""
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

function flush_stanza(   i, pos_inject, meaningful) {

  if (n==0) return

  # Non-correlation stanzas: copy as-is
  if (!has_corr) {
    print_raw_stanza()
    delete lines; n=0
    reset_flags()
    return
  }

  # Correlation stanza but no header name (should not happen): copy as-is
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

  # For notable/risk injection: after rule_title if present, else after label, else after header
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

# stanza boundary: blank line
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

  # Track presence of plain description
  if (line ~ /^[[:space:]]*description[[:space:]]*=/)
    has_plain_desc=1

  # Track presence of plain description
  if (line ~ /^[[:space:]]*description[[:space:]]*=/)
    has_plain_desc=1

  # Track presence of notable rule_description
  if (line ~ /^[[:space:]]*action\.notable\.param\.rule_description[[:space:]]*=/)
    has_desc=1

  # Track presence of notable rule_title
  if (line ~ /^[[:space:]]*action\.notable\.param\.rule_title[[:space:]]*=/)
    has_rule_title=1

  # Track presence of investigation_type
  if (line ~ /^[[:space:]]*action\.notable\.param\.investigation_type[[:space:]]*=/)
    has_invest=1

  # Track presence of risk message
  if (line ~ /^[[:space:]]*action\.risk\.param\._risk_message[[:space:]]*=/)
    has_risk=1
}

END { flush_stanza() }
' "$IN" > "$OUT"