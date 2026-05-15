# 2B_lora vs 4B_lora Per-Sample Diff Analysis

- Source 2B: `ab_eval_predictions_2B_2B_lora_deployment.jsonl` (409 samples)
- Source 4B: `ab_eval_predictions_4B_4B_lora_deployment.jsonl` (409 samples)
- Aligned samples: 409

## 1. Four-Quadrant Statistics

| Metric | Both Correct | 2B Wrong 4B Correct | 2B Correct 4B Wrong | Both Wrong |
|--------|-------------|---------------------|---------------------|------------|
| **Category Exact Match** | 377 | 15 | 9 | 8 |
| **Defect Type Exact Match** | 176 | 89 | 41 | 103 |
| **BBox IoU >= 0.5** | 169 | 95 | 31 | 114 |

**Truncation note** (output_tokens >= 200):

- Category Exact Match: 27 truncated samples (only_4b=10, only_2b=9, neither=8)
- Defect Type Exact Match: 27 truncated samples (only_4b=9, only_2b=6, neither=12)
- BBox IoU >= 0.5: 27 truncated samples (only_4b=6, only_2b=5, neither=16)

Truncated samples are counted in the quadrant table above but flagged separately — 
their failures may be caused by output cutoff rather than model capability.

## 2. Both Wrong Samples (defect_type_exact)

### bottle (3 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| broken_small_008.png | broken_small | broken_large | broken_large | 0.5152 | 0.0201 |  |
| broken_small_014.png | broken_small | contamination | contamination | 0.3704 | 0.5153 |  |
| contamination_003.png | contamination | broken_small | broken_small | 0.142 | 0.8299 |  |

### cable (13 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| bent_wire_001.png | bent_wire | miswound | missing_wire | 0.1242 | 0.8176 |  |
| bent_wire_004.png | bent_wire | cut_outer_insulation | cut_wire | 0.3421 | 0.7003 |  |
| cable_swap_002.png | cable_swap | cable_interior | combined | 0.4749 | 0.0307 |  |
| cable_swap_011.png | cable_swap | missing_cable | squeeze | 0.3343 | 0.1024 |  |
| combined_000.png | combined | cut_outer_insulation | bent_wire | 0.0684 | 0.8694 |  |
| combined_003.png | combined | cable_interior_defect | squeeze | 0.2674 | 0.0731 |  |
| combined_005.png | combined | missing_cable | missing_cable | 0.5484 | 0.5111 |  |
| combined_010.png | combined | missing_cable | missing_cable | 0.3987 | 0.8517 |  |
| missing_wire_001.png | missing_wire | cable_interior | cut_inner_insulation | 0.2147 | 0.8905 |  |
| missing_wire_006.png | missing_wire | cut_outer_insulation | missing_cable | 0.2545 | 0.2436 |  |
| missing_wire_009.png | missing_wire | cable_interior | cut_inner_insulation | 0.318 | 0.2872 |  |
| poke_insulation_004.png | poke_insulation | bent_insulation | squeeze | 0.418 | 0.2705 |  |
| poke_insulation_008.png | poke_insulation | cut_outer_insulation | bent_wire | 0.3492 | 0.0 |  |

### capsule (9 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| crack_005.png | crack | scratch | scratch | 0.3864 | 0.5196 |  |
| crack_008.png | crack | poke | scratch | 0.4057 | 0.2111 |  |
| crack_016.png | crack | faulty_imprint | poke | 0.3776 | 0.7313 |  |
| crack_018.png | crack | scratch | scratch | 0.5276 | 0.7512 |  |
| poke_006.png | poke | scratch | faulty_imprint | 0.7207 | 0.6508 |  |
| poke_011.png | poke | scratch | scratch | 0.6208 | 0.8752 |  |
| poke_017.png | poke | faulty_imprint | faulty_imprint | 0.4187 | 0.55 |  |
| squeeze_003.png | squeeze | poke | poke | 0.4237 | 0.4388 |  |
| squeeze_005.png | squeeze | crack | crack | 0.0 | 0.0439 |  |

### carpet (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| cut_014.png | cut | hole | hole | 0.2833 | 0.6995 |  |
| hole_000.png | hole | cut | cut | 0.6706 | 0.5878 |  |
| hole_004.png | hole | cut | cut | 0.5053 | 0.7316 |  |
| hole_016.png | hole | thread | thread | 0.3066 | 0.2713 |  |

### grid (7 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| broken_000.png | broken | cut | bent | 0.3247 | 0.6162 |  |
| broken_008.png | broken | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| broken_010.png | broken | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| glue_008.png | glue | (parse_fail) | bent | 0.0 | 0.0 | Y |
| metal_contamination_004.png | metal_contamination | glue | glue | 0.532 | 0.6386 |  |
| thread_002.png | thread | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| thread_009.png | thread | cut | bent | 0.0163 | 0.0055 |  |

### hazelnut (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| crack_004.png | crack | hole | cut | 0.476 | 0.9183 |  |
| cut_008.png | cut | crack | crack | 0.2053 | 0.6987 |  |
| print_001.png | print | color | paint | 0.6974 | 0.8554 |  |
| print_004.png | print | glue | (parse_fail) | 0.5156 | 0.0 | Y |

### leather (5 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| cut_000.png | cut | poke | poke | 0.5781 | 0.6845 |  |
| fold_006.png | fold | poke | poke | 0.2601 | 0.2807 |  |
| glue_010.png | glue | color | color | 0.7521 | 0.8934 |  |
| glue_016.png | glue | color | color | 0.7414 | 0.8442 |  |
| poke_009.png | poke | hole | hole | 0.6256 | 0.63 |  |

### metal_nut (3 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| color_017.png | color | scratch | scratch | 0.5482 | 0.8495 |  |
| flip_010.png | flip | bent | bent | 0.0 | 0.0 |  |
| scratch_015.png | scratch | flip | bent | 0.1081 | 0.7501 |  |

### pill (14 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| color_012.png | color | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| combined_004.png | combined | scratch | (parse_fail) | 0.6272 | 0.0 | Y |
| combined_006.png | combined | crack | contamination | 0.6335 | 0.5831 |  |
| combined_012.png | combined | crack | crack | 0.5418 | 0.3087 |  |
| combined_013.png | combined | crack | crack | 0.7254 | 0.8025 |  |
| combined_016.png | combined | crack | crack | 0.8828 | 0.6968 |  |
| contamination_006.png | contamination | combined | crack | 0.5394 | 0.8948 |  |
| contamination_007.png | contamination | crack | crack | 0.7896 | 0.9394 |  |
| faulty_imprint_006.png | faulty_imprint | crack | scratch | 0.4263 | 0.4088 |  |
| scratch_010.png | scratch | crack | contamination | 0.8016 | 0.6658 |  |
| scratch_012.png | scratch | combined | contamination | 0.779 | 0.7674 |  |
| scratch_019.png | scratch | contamination | contamination | 0.7506 | 0.8437 |  |
| scratch_021.png | scratch | color | crack | 0.8158 | 0.8355 |  |
| scratch_022.png | scratch | contamination | contamination | 0.7469 | 0.6434 |  |

### screw (12 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| manipulated_front_000.png | manipulated_front | thread_top | thread_top | 0.0 | 0.0614 |  |
| manipulated_front_002.png | manipulated_front | thread_top | thread_top | 0.1265 | 0.0993 |  |
| manipulated_front_020.png | manipulated_front | thread_top | thread_top | 0.0368 | 0.1259 |  |
| manipulated_front_023.png | manipulated_front | thread_top | thread_side | 0.1358 | 0.0911 |  |
| scratch_head_009.png | scratch_head | manipulated_head | thread_top | 0.3105 | 0.4469 |  |
| scratch_neck_005.png | scratch_neck | thread_top | thread_side | 0.2879 | 0.0 |  |
| thread_side_008.png | thread_side | scratch_head | scratch_neck | 0.0 | 0.0 |  |
| thread_side_012.png | thread_side | thread_top | thread_top | 0.0 | 0.139 |  |
| thread_top_009.png | thread_top | scratch_neck | thread_side | 0.0 | 0.7965 |  |
| thread_top_012.png | thread_top | scratch_neck | thread_side | 0.0 | 0.0 |  |
| thread_top_014.png | thread_top | scratch_neck | scratch_neck | 0.0 | 0.0 |  |
| thread_top_016.png | thread_top | scratch_neck | manipulated_front | 0.0 | 0.0 |  |

### tile (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| glue_strip_007.png | glue_strip | crack | crack | 0.7064 | 0.9836 |  |
| rough_001.png | rough | gray_stripe | gray_stroke | 0.547 | 0.7194 |  |
| rough_007.png | rough | gray_stroke | gray_stroke | 0.3972 | 0.3356 |  |
| rough_013.png | rough | crack | scratch | 0.7614 | 0.7932 |  |

### transistor (6 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| cut_lead_000.png | cut_lead | bent_lead | bent_lead | 0.0 | 0.0 |  |
| cut_lead_001.png | cut_lead | scratch | bent_lead | 0.0 | 0.1879 |  |
| cut_lead_003.png | cut_lead | bent_lead | bent_lead | 0.0 | 0.0 |  |
| misplaced_004.png | misplaced | bent_lead | scratch_lead | 0.1051 | 0.0931 |  |
| misplaced_006.png | misplaced | bent_lead | scratch_case | 0.0275 | 0.0 |  |
| misplaced_008.png | misplaced | bent_lead | cut_lead | 0.0 | 0.1053 |  |

### wood (7 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| combined_005.png | combined | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| combined_006.png | combined | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| combined_008.png | combined | scratch | scratch | 0.8656 | 0.9653 |  |
| hole_002.png | hole | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |
| liquid_006.png | liquid | color | glue | 0.7085 | 0.8631 |  |
| scratch_001.png | scratch | edge | combined | 0.6655 | 0.1719 |  |
| scratch_015.png | scratch | (parse_fail) | (parse_fail) | 0.0 | 0.0 | Y |

### zipper (12 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | 2B IoU | 4B IoU | Truncated |
|-------|---------------|---------------|---------------|--------|--------|-----------|
| broken_teeth_002.png | broken_teeth | combined | rough | 0.585 | 0.4029 |  |
| broken_teeth_008.png | broken_teeth | split_teeth | split_teeth | 0.377 | 0.5756 |  |
| broken_teeth_009.png | broken_teeth | squeezed_teeth | (parse_fail) | 0.3494 | 0.0 | Y |
| broken_teeth_010.png | broken_teeth | split | rough | 0.3668 | 0.3312 |  |
| broken_teeth_011.png | broken_teeth | split_teeth | rough | 0.1765 | 0.5392 |  |
| broken_teeth_015.png | broken_teeth | squeezed_teeth | squeezed_teeth | 0.109 | 0.6352 |  |
| combined_003.png | combined | fabric_front | fabric_interior | 0.8227 | 0.5081 |  |
| combined_014.png | combined | split_teeth | rough | 0.1255 | 0.9052 |  |
| fabric_border_005.png | fabric_border | combined | thread | 0.787 | 0.8564 |  |
| fabric_border_014.png | fabric_border | fabric_front | cut_thread | 0.5599 | 0.8347 |  |
| squeezed_teeth_010.png | squeezed_teeth | rough | rough | 0.3229 | 0.3107 |  |
| squeezed_teeth_014.png | squeezed_teeth | split_teeth | split_teeth | 0.5837 | 0.5563 |  |

## 3. 2B Wrong but 4B Correct Samples (defect_type_exact)

### bottle (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| broken_large_000.png | broken_large | broken_small | broken_large |  |
| contamination_008.png | contamination | bubble | contamination |  |
| contamination_011.png | contamination | broken_large | contamination |  |
| contamination_016.png | contamination | broken_small | contamination |  |

### cable (8 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| bent_wire_006.png | bent_wire | cut_outer_insulation | bent_wire |  |
| cable_swap_001.png | cable_swap | cut_inner_insulation | cable_swap |  |
| cable_swap_010.png | cable_swap | cable_interior | cable_swap |  |
| cut_inner_insulation_003.png | cut_inner_insulation | cut_outer_insulation | cut_inner_insulation |  |
| cut_inner_insulation_009.png | cut_inner_insulation | cut_outer_insulation | cut_inner_insulation |  |
| cut_outer_insulation_004.png | cut_outer_insulation | bent | cut_outer_insulation |  |
| cut_outer_insulation_008.png | cut_outer_insulation | cut_inner_insulation | cut_outer_insulation |  |
| cut_outer_insulation_009.png | cut_outer_insulation | cut_inner_insulation | cut_outer_insulation |  |

### capsule (8 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| crack_000.png | crack | scratch | crack |  |
| faulty_imprint_011.png | faulty_imprint | squeeze | faulty_imprint |  |
| poke_007.png | poke | squeeze | poke |  |
| poke_009.png | poke | scratch | poke |  |
| poke_012.png | poke | scratch | poke |  |
| scratch_001.png | scratch | faulty_imprint | scratch |  |
| squeeze_006.png | squeeze | crack | squeeze |  |
| squeeze_017.png | squeeze | crack | squeeze |  |

### carpet (5 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| hole_006.png | hole | cut | hole |  |
| hole_009.png | hole | cut | hole |  |
| metal_contamination_005.png | metal_contamination | (parse_fail) | metal_contamination | Y |
| thread_008.png | thread | cut | thread |  |
| thread_010.png | thread | cut | thread |  |

### grid (8 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| bent_002.png | bent | combined | bent |  |
| bent_004.png | bent | cut | bent |  |
| bent_005.png | bent | squeezed | bent |  |
| glue_004.png | glue | liquid | glue |  |
| glue_010.png | glue | liquid | glue |  |
| metal_contamination_000.png | metal_contamination | glue | metal_contamination |  |
| metal_contamination_008.png | metal_contamination | (parse_fail) | metal_contamination | Y |
| thread_004.png | thread | (parse_fail) | thread | Y |

### hazelnut (6 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| crack_008.png | crack | hole | crack |  |
| cut_003.png | cut | poke | cut |  |
| hole_007.png | hole | poke | hole |  |
| hole_008.png | hole | poke | hole |  |
| print_000.png | print | glare | print |  |
| print_015.png | print | scratch | print |  |

### leather (3 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| cut_017.png | cut | (parse_fail) | cut | Y |
| glue_017.png | glue | glue_strip | glue |  |
| poke_013.png | poke | cut | poke |  |

### metal_nut (1 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| bent_004.png | bent | scratch | bent |  |

### pill (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| contamination_010.png | contamination | crack | contamination |  |
| faulty_imprint_013.png | faulty_imprint | crack | faulty_imprint |  |
| scratch_000.png | scratch | crack | scratch |  |
| scratch_018.png | scratch | faulty_imprint | scratch |  |

### screw (14 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| manipulated_front_007.png | manipulated_front | thread_top | manipulated_front |  |
| manipulated_front_017.png | manipulated_front | thread_top | manipulated_front |  |
| scratch_head_003.png | scratch_head | thread_top | scratch_head |  |
| scratch_head_011.png | scratch_head | scratch_neck | scratch_head |  |
| scratch_neck_000.png | scratch_neck | scratch_head | scratch_neck |  |
| scratch_neck_011.png | scratch_neck | scratch_head | scratch_neck |  |
| scratch_neck_017.png | scratch_neck | thread_top | scratch_neck |  |
| scratch_neck_024.png | scratch_neck | scratch_head | scratch_neck |  |
| thread_side_001.png | thread_side | thread_top | thread_side |  |
| thread_side_002.png | thread_side | thread_top | thread_side |  |
| thread_side_003.png | thread_side | scratch_neck | thread_side |  |
| thread_side_005.png | thread_side | thread_top | thread_side |  |
| thread_side_015.png | thread_side | scratch_neck | thread_side |  |
| thread_top_018.png | thread_top | scratch_head | thread_top |  |

### tile (7 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| glue_strip_003.png | glue_strip | (parse_fail) | glue_strip | Y |
| glue_strip_004.png | glue_strip | crack | glue_strip |  |
| glue_strip_010.png | glue_strip | glue | glue_strip |  |
| glue_strip_013.png | glue_strip | broken | glue_strip |  |
| oil_000.png | oil | flip | oil |  |
| oil_003.png | oil | flip_side | oil |  |
| oil_009.png | oil | glue | oil |  |

### toothbrush (3 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| defective_009.png | defective | (parse_fail) | defective | Y |
| defective_012.png | defective | (parse_fail) | defective | Y |
| defective_014.png | defective | (parse_fail) | defective | Y |

### transistor (3 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| damaged_case_001.png | damaged_case | cut_top | damaged_case |  |
| damaged_case_003.png | damaged_case | scratch | damaged_case |  |
| damaged_case_009.png | damaged_case | broken_case | damaged_case |  |

### wood (4 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| combined_004.png | combined | scratch | combined |  |
| liquid_003.png | liquid | glue | liquid |  |
| liquid_009.png | liquid | water | liquid |  |
| scratch_018.png | scratch | (parse_fail) | scratch | Y |

### zipper (11 samples)

| Image | GT defect_type | 2B prediction | 4B prediction | Truncated |
|-------|---------------|---------------|---------------|-----------|
| fabric_border_001.png | fabric_border | fabric_front | fabric_border |  |
| fabric_border_002.png | fabric_border | fabric_front | fabric_border |  |
| fabric_border_006.png | fabric_border | combined | fabric_border |  |
| fabric_border_009.png | fabric_border | fabric_front | fabric_border |  |
| fabric_interior_002.png | fabric_interior | combined | fabric_interior |  |
| fabric_interior_003.png | fabric_interior | combined | fabric_interior |  |
| fabric_interior_009.png | fabric_interior | contamination | fabric_interior |  |
| fabric_interior_014.png | fabric_interior | fabric | fabric_interior |  |
| rough_010.png | rough | split_teeth | rough |  |
| split_teeth_000.png | split_teeth | broken_teeth | split_teeth |  |
| squeezed_teeth_011.png | squeezed_teeth | split_teeth | squeezed_teeth |  |

## 4. Truncation Summary

- 2B_lora truncated samples (output_tokens >= 200): **18**
- 4B_lora truncated samples (output_tokens >= 200): **17**

| Category | 2B truncated | 4B truncated |
|----------|-------------|-------------|
| carpet | 1 | 0 |
| grid | 6 | 4 |
| hazelnut | 0 | 1 |
| leather | 1 | 0 |
| pill | 1 | 4 |
| tile | 1 | 0 |
| toothbrush | 3 | 2 |
| wood | 5 | 4 |
| zipper | 0 | 2 |
