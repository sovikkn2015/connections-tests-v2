%dw 2.0
// Project 006 v3 - OFAC SDN beneficiary name screen.
//
// Input: the OFAC SDN XML document as payload (fetched by the flow).
//         vars.beneficiaryName: the raw string from the request.
// Output: { matched: Boolean, matched_name: String | null }
//
// Lightweight exact-match on the canonical beneficiary name against the
// full SDN entity list. Production screeners add fuzzy matching + AKA
// handling; this is a deterministic gate appropriate for v3's paper/sandbox
// scope. A real Treasury-grade screen is out of scope for the demo.
//
// The SDN XML shape is:
//   <sdnList>
//     <sdnEntry>
//       <sdnType>Individual|Entity|Vessel|Aircraft</sdnType>
//       <firstName>...</firstName>
//       <lastName>...</lastName>
//       ...
//     </sdnEntry>
//     ...
//   </sdnList>
//
// We match against "firstName lastName" for Individual and "lastName" alone
// for Entity/Vessel/Aircraft (OFAC stores the legal name in lastName for
// non-Individual entries).
import upper, trim from dw::core::Strings
output application/json
var needle = upper(trim(vars.beneficiaryName default ""))
var entries = (payload.sdnList.*sdnEntry default [])
var names = entries map ((e) ->
  upper(trim(
    if ((e.sdnType default "") == "Individual")
      ((e.firstName default "") ++ " " ++ (e.lastName default ""))
    else
      (e.lastName default "")
  ))
)
var hit = names filter ($ != "" and $ == needle)
---
{
  matched: sizeOf(hit) > 0,
  matched_name: if (sizeOf(hit) > 0) hit[0] else null
}
