#!/usr/bin/env bash
# whatsapp_smoke.sh — drive the Meta WhatsApp Cloud API by hand, from a phone.
#
# WHY THIS EXISTS. WhatsApp Manager shows the number as "Pending" with
# "register this phone number using the registration API". That is not the
# SMS/voice OTP failing — the OTP only proves you own the number. Registration
# is a SEPARATE API call that nothing in the Meta UI will make for you, and
# until it succeeds the number cannot send or receive anything. "Contact your
# partner" in that tooltip is boilerplate Meta shows on every number; for a
# direct (non-BSP) integration like ours it does not apply.
#
# Runs in Termux with nothing but curl and jq:
#     pkg install curl jq
#
# SECRETS NEVER LIVE IN THIS FILE. Export them in the shell you run it from,
# or keep them in a file you chmod 600 and never commit:
#
#     export WA_TOKEN=...        # System User token (or the 24h temp one)
#     export WA_WABA_ID=...      # Business Settings > WhatsApp accounts > ID
#     export WA_PIN=......       # a 6-digit PIN YOU choose; write it down
#     export WA_TO=+9198xxxxxxxx # a test recipient, E.164
#
# WA_PHONE_ID is discovered by `numbers` — it is NOT the phone number.
#
# Usage:
#     ./whatsapp_smoke.sh me           who does this token belong to
#     ./whatsapp_smoke.sh numbers      the WABA's numbers + their status + IDs
#     ./whatsapp_smoke.sh register     the call that clears "Pending"   [changes state]
#     ./whatsapp_smoke.sh templates    which templates exist and are APPROVED
#     ./whatsapp_smoke.sh send-text    free-form reply (only inside a 24h window)  [costs]
#     ./whatsapp_smoke.sh send-template NAME [LANG] [PARAM...]                     [costs]
#
# The three marked steps do something real: `register` changes the number's
# state with Meta, and both sends are billed conversations. They each stop and
# ask before acting.
set -u -o pipefail

GRAPH="https://graph.facebook.com/v21.0"

die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }
note() { printf '\033[36m%s\033[0m\n' "$*"; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing $1 — run: pkg install $1"; }
need curl; need jq

req() {
  : "${WA_TOKEN:?export WA_TOKEN first (see the header of this script)}"
}

# Prints the body; returns non-zero and explains when Meta reports an error.
call() {
  local method=$1 url=$2; shift 2
  local body status
  body=$(curl -sS -w '\n%{http_code}' -X "$method" "$url" \
           -H "Authorization: Bearer $WA_TOKEN" "$@") || die "curl failed — no network?"
  status=${body##*$'\n'}
  body=${body%$'\n'*}
  if [ "$status" -ge 400 ]; then
    printf '\033[31mHTTP %s\033[0m\n' "$status" >&2
    printf '%s\n' "$body" | jq '.error | {code, error_subcode, type, message, error_user_msg}' >&2 2>/dev/null \
      || printf '%s\n' "$body" >&2
    return 1
  fi
  printf '%s\n' "$body"
}

confirm() {
  printf '\033[33m%s\033[0m\n' "$1"
  printf 'type yes to go ahead: '
  read -r answer
  [ "$answer" = "yes" ] || die "stopped."
}

cmd=${1:-numbers}; shift || true
req

case "$cmd" in

me)
  # Cheapest possible proof the token is alive and what it can reach. A token
  # that has expired fails HERE rather than three calls later with a confusing
  # "unsupported get request".
  call GET "$GRAPH/me" | jq .
  note "If this printed an id, the token is valid. A 190 error means it expired —"
  note "the temporary API Setup token lasts 24 hours; generate a System User token."
  ;;

numbers)
  : "${WA_WABA_ID:?export WA_WABA_ID (Business Settings > WhatsApp accounts > the ID under the name)}"
  call GET "$GRAPH/$WA_WABA_ID/phone_numbers?fields=id,display_phone_number,verified_name,code_verification_status,platform_type,quality_rating,status" \
    | jq -r '.data[] | "id=\(.id)  \(.display_phone_number)  \(.verified_name)  status=\(.status // "?")  verification=\(.code_verification_status // "?")"'
  note ""
  note "The 'id=' value is WA_PHONE_ID — export it. It is not the phone number."
  note "status=PENDING means the registration call below has not been made."
  ;;

register)
  : "${WA_PHONE_ID:?export WA_PHONE_ID — run './whatsapp_smoke.sh numbers' to find it}"
  : "${WA_PIN:?export WA_PIN — six digits YOU choose}"
  case "$WA_PIN" in
    [0-9][0-9][0-9][0-9][0-9][0-9]) ;;
    *) die "WA_PIN must be exactly six digits." ;;
  esac
  confirm "About to register $WA_PHONE_ID on the Cloud API and set its two-step PIN.
This PIN becomes the number's permanent two-step verification PIN — you will
need it again to re-register or migrate the number. Write it down FIRST."
  call POST "$GRAPH/$WA_PHONE_ID/register" \
    -H 'Content-Type: application/json' \
    -d "{\"messaging_product\":\"whatsapp\",\"pin\":\"$WA_PIN\"}" | jq .
  note ""
  note '{"success": true} means done. Re-run `numbers` — status flips to CONNECTED,'
  note "and WhatsApp Manager stops saying Pending after a refresh."
  note "Error 133005 = wrong PIN for a number already registered."
  note "Error 133006 = the number still needs its SMS/voice OTP first."
  ;;

templates)
  : "${WA_WABA_ID:?export WA_WABA_ID}"
  call GET "$GRAPH/$WA_WABA_ID/message_templates?fields=name,status,category,language&limit=50" \
    | jq -r '.data[] | "\(.status)\t\(.category)\t\(.language)\t\(.name)"' | sort
  note ""
  note "Only APPROVED templates can be sent. A template send to a PENDING or"
  note "REJECTED name fails with a 132xxx error and is not billed."
  ;;

send-text)
  # Free-form text only works inside the 24-hour customer service window — i.e.
  # the recipient must have messaged the business first. Outside it Meta returns
  # 131047 and nothing is delivered. This is the cheapest real send to try, so
  # message the business number from your own WhatsApp, then run this.
  : "${WA_PHONE_ID:?export WA_PHONE_ID}"
  : "${WA_TO:?export WA_TO — a recipient in E.164, e.g. +919876543210}"
  msg=${1:-"DGE smoke test — ignore."}
  confirm "Send a free-form text to $WA_TO. This opens/uses a billed service
conversation. It only works if $WA_TO messaged the business number in the last
24 hours; otherwise Meta answers 131047 and charges nothing."
  call POST "$GRAPH/$WA_PHONE_ID/messages" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg to "${WA_TO#+}" --arg body "$msg" \
          '{messaging_product:"whatsapp",recipient_type:"individual",to:$to,type:"text",text:{body:$body}}')" \
    | jq .
  ;;

send-template)
  : "${WA_PHONE_ID:?export WA_PHONE_ID}"
  : "${WA_TO:?export WA_TO}"
  name=${1:?usage: send-template NAME [LANG] [PARAM...]}
  lang=${2:-en}
  shift 2 2>/dev/null || shift 1
  params=$(printf '%s\n' "$@" | jq -R . | jq -sc 'map(select(. != "")) | map({type:"text",text:.})')
  if [ "$params" = "[]" ]; then
    tmpl=$(jq -nc --arg n "$name" --arg l "$lang" '{name:$n,language:{code:$l}}')
  else
    tmpl=$(jq -nc --arg n "$name" --arg l "$lang" --argjson p "$params" \
           '{name:$n,language:{code:$l},components:[{type:"body",parameters:$p}]}')
  fi
  confirm "Send template '$name' ($lang) to $WA_TO. A template send is billed
whether or not the recipient reads it, and reaches someone who never messaged
us — so make sure $WA_TO is your own number."
  call POST "$GRAPH/$WA_PHONE_ID/messages" \
    -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg to "${WA_TO#+}" --argjson t "$tmpl" \
          '{messaging_product:"whatsapp",recipient_type:"individual",to:$to,type:"template",template:$t}')" \
    | jq .
  note ""
  note "An authentication template with a copy-code button ALSO needs a button"
  note "component carrying the same code; this sends body parameters only, which"
  note "is the utility/broadcast shape. lib/whatsapp.js builds the auth shape."
  ;;

*) die "unknown command: $cmd — run with no arguments to see usage in the header." ;;
esac
