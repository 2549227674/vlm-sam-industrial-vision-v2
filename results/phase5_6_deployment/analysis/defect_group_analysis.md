# Defect Group Exact Analysis

## Alias Group Definitions

- **cable**:
  - `insulation_defect`: cut_inner_insulation, cut_outer_insulation, poke_insulation
  - `wire_defect`: bent_wire, cut_wire, missing_wire
- **capsule**:
  - `surface_scratch_crack`: crack, scratch
- **carpet**:
  - `opening_defect`: cut, hole
- **pill**:
  - `surface_scratch_crack`: crack, scratch
- **screw**:
  - `screw_thread`: thread_side, thread_top
  - `screw_scratch`: scratch_head, scratch_neck
  - `manipulation`: manipulated_front
- **zipper**:
  - `fabric_defect`: fabric_border, fabric_front, fabric_interior
  - `teeth_defect`: broken_teeth, rough, split_teeth, squeezed_teeth

## Overall Comparison

| Variant | Total | type_exact | type_exact_% | group_exact | group_applicable | group_exact_% | Delta |
|---------|-------|-----------|-------------|-------------|-----------------|--------------|-------|
| 2B_base | 409 | 46/409 | 11.2% | 37/132 | 132 | 28.0% | +16.8% |
| 2B_lora | 409 | 217/409 | 53.1% | 89/132 | 132 | 67.4% | +14.4% |
| 4B_base | 409 | 43/409 | 10.5% | 28/132 | 132 | 21.2% | +10.7% |
| 4B_lora | 409 | 265/409 | 64.8% | 102/132 | 132 | 77.3% | +12.5% |

## Per-Category Breakdown

### cable

Groups: `insulation_defect` (cut_inner_insulation, cut_outer_insulation, poke_insulation), `wire_defect` (bent_wire, cut_wire, missing_wire)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 30 | 0/30 | 0.0% | 0/18 | 18 | 0.0% | +0.0% |
| 2B_lora | 30 | 9/30 | 30.0% | 10/18 | 18 | 55.6% | +25.6% |
| 4B_base | 30 | 0/30 | 0.0% | 0/18 | 18 | 0.0% | +0.0% |
| 4B_lora | 30 | 12/30 | 40.0% | 11/18 | 18 | 61.1% | +21.1% |

### capsule

Groups: `surface_scratch_crack` (crack, scratch)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 34 | 7/34 | 20.6% | 14/14 | 14 | 100.0% | +79.4% |
| 2B_lora | 34 | 17/34 | 50.0% | 11/14 | 14 | 78.6% | +28.6% |
| 4B_base | 34 | 7/34 | 20.6% | 14/14 | 14 | 100.0% | +79.4% |
| 4B_lora | 34 | 22/34 | 64.7% | 13/14 | 14 | 92.9% | +28.2% |

### carpet

Groups: `opening_defect` (cut, hole)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 30 | 4/30 | 13.3% | 7/12 | 12 | 58.3% | +45.0% |
| 2B_lora | 30 | 21/30 | 70.0% | 11/12 | 12 | 91.7% | +21.7% |
| 4B_base | 30 | 3/30 | 10.0% | 4/12 | 12 | 33.3% | +23.3% |
| 4B_lora | 30 | 23/30 | 76.7% | 11/12 | 12 | 91.7% | +15.0% |

### pill

Groups: `surface_scratch_crack` (crack, scratch)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 46 | 8/46 | 17.4% | 16/16 | 16 | 100.0% | +82.6% |
| 2B_lora | 46 | 28/46 | 60.9% | 11/16 | 16 | 68.8% | +7.9% |
| 4B_base | 46 | 5/46 | 10.9% | 10/16 | 16 | 62.5% | +51.6% |
| 4B_lora | 46 | 25/46 | 54.3% | 11/16 | 16 | 68.8% | +14.4% |

### screw

Groups: `manipulation` (manipulated_front), `screw_scratch` (scratch_head, scratch_neck), `screw_thread` (thread_side, thread_top)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 38 | 0/38 | 0.0% | 0/38 | 38 | 0.0% | +0.0% |
| 2B_lora | 38 | 12/38 | 31.6% | 20/38 | 38 | 52.6% | +21.1% |
| 4B_base | 38 | 0/38 | 0.0% | 0/38 | 38 | 0.0% | +0.0% |
| 4B_lora | 38 | 22/38 | 57.9% | 26/38 | 38 | 68.4% | +10.5% |

### zipper

Groups: `fabric_defect` (fabric_border, fabric_front, fabric_interior), `teeth_defect` (broken_teeth, rough, split_teeth, squeezed_teeth)

| Variant | Total | type_exact | type_% | group_exact | group_applicable | group_% | Delta |
|---------|-------|-----------|-------|-------------|-----------------|---------|-------|
| 2B_base | 39 | 0/39 | 0.0% | 0/34 | 34 | 0.0% | +0.0% |
| 2B_lora | 39 | 16/39 | 41.0% | 26/34 | 34 | 76.5% | +35.4% |
| 4B_base | 39 | 0/39 | 0.0% | 0/34 | 34 | 0.0% | +0.0% |
| 4B_lora | 39 | 22/39 | 56.4% | 30/34 | 34 | 88.2% | +31.8% |

## Non-Aliased Categories

These categories have no alias groups defined; defect_type_exact == defect_group_exact.

| Variant | Category | type_exact | type_% |
|---------|----------|-----------|-------|
| 2B_base | bottle | 0/20 | 0.0% |
| 2B_lora | bottle | 13/20 | 65.0% |
| 4B_base | bottle | 0/20 | 0.0% |
| 4B_lora | bottle | 11/20 | 55.0% |
| 2B_base | grid | 0/20 | 0.0% |
| 2B_lora | grid | 5/20 | 25.0% |
| 4B_base | grid | 2/20 | 10.0% |
| 4B_lora | grid | 12/20 | 60.0% |
| 2B_base | hazelnut | 7/24 | 29.2% |
| 2B_lora | hazelnut | 14/24 | 58.3% |
| 4B_base | hazelnut | 8/24 | 33.3% |
| 4B_lora | hazelnut | 19/24 | 79.2% |
| 2B_base | leather | 0/30 | 0.0% |
| 2B_lora | leather | 22/30 | 73.3% |
| 4B_base | leather | 0/30 | 0.0% |
| 4B_lora | leather | 23/30 | 76.7% |
| 2B_base | metal_nut | 9/29 | 31.0% |
| 2B_lora | metal_nut | 25/29 | 86.2% |
| 4B_base | metal_nut | 9/29 | 31.0% |
| 4B_lora | metal_nut | 25/29 | 86.2% |
| 2B_base | tile | 6/28 | 21.4% |
| 2B_lora | tile | 17/28 | 60.7% |
| 4B_base | tile | 3/28 | 10.7% |
| 4B_lora | tile | 23/28 | 82.1% |
| 2B_base | toothbrush | 0/9 | 0.0% |
| 2B_lora | toothbrush | 6/9 | 66.7% |
| 4B_base | toothbrush | 0/9 | 0.0% |
| 4B_lora | toothbrush | 7/9 | 77.8% |
| 2B_base | transistor | 0/12 | 0.0% |
| 2B_lora | transistor | 3/12 | 25.0% |
| 4B_base | transistor | 0/12 | 0.0% |
| 4B_lora | transistor | 6/12 | 50.0% |
| 2B_base | wood | 5/20 | 25.0% |
| 2B_lora | wood | 9/20 | 45.0% |
| 4B_base | wood | 6/20 | 30.0% |
| 4B_lora | wood | 13/20 | 65.0% |
