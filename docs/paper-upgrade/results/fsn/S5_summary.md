# S5: knowledge-layer resolution tiers (generated)

458 VLM answers from S2 (unhinted + hinted), 188 distinct (name, ground-truth) pairs.
Tier counts (all answers): {'miss': 152, 'exact': 276, 'partial': 30}
Tier counts (distinct pairs): {'miss': 89, 'exact': 86, 'partial': 13}
Rows where tier logic disagrees with shared.food_lookup.lookup_food: 0

`canonical_matches_gt` is the automatic check; `manual_verdict` is left blank in S5_lookup_tiers.csv for a human. Check below: partial-tier resolutions (the riskiest tier):

| ground truth | VLM name | resolved canonical food | canonical matches gt |
|---|---|---|---|
| bell pepper | pepper | Bell Pepper | True |
| chicken | gizzard | Chicken Gizzards | False |
| coconutchutney | chutney | Coconutchutney | True |
| grape | rice | Rice -Chamal- | False |
| greenchutney | chutney | Coconutchutney | False |
| hot pepper | pepper | Bell Pepper | False |
| hot pepper | chili | Chili Pepper -Khursani- | True |
| palakpaneer | paneer | Palakpaneer | True |
| rajmacurry | chili | Chili Pepper -Khursani- | False |
| red lentils | lentils | Green Lentils | False |
| rice -chamal- | rice | Rice -Chamal- | True |
| shahipaneer | paneer | Palakpaneer | False |
| whiterice | rice | Rice -Chamal- | True |

Exact tier: 56 of 86 distinct pairs resolve to the ground-truth food (the remainder are cases where the VLM name itself was wrong and was resolved faithfully to that wrong food).
Partial tier: 6 of 13 resolve to the ground-truth food; e.g. 'paneer' -> Palakpaneer, 'chutney' -> Coconutchutney, 'pepper' -> Bell Pepper are wrong-food resolutions for other ground truths.
