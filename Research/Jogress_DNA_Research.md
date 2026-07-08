# Jogress / DNA Evolution Notes

This note records how official Time Stranger data encodes Jogress / DNA evolution.

## Encoding

Jogress / DNA is not a separate `evolution_to` type.

- `evolution_to` has one normal source edge per partner:
  - column 1: source Digimon ID
  - column 3: target Digimon ID
  - column 5: path type, usually `0` for normal/DNA source edges
- `evolution_condition` marks the target as Jogress / DNA:
  - column 0: target Digimon ID
  - column 24: partner A Digimon ID
  - column 26: partner A personality
  - column 27: partner B Digimon ID
  - column 29: partner B personality

Mode Change uses `evolution_to` column 5 value `2`; this is separate from Jogress / DNA.

## Checked Official Examples

All of these use two `evolution_to` rows with type `0`, plus one target condition row with partner IDs:

| Target | Partners | Mode | Notes |
|---|---|---:|---|
| 915 Titamon + SkullBaluchimon | 440 Titamon p4 + 239 SkullBaluchimon p10 | 8 | Base condition row 450 |
| 215 Examon | 213 Slayerdramon p3 + 214 Breakdramon p4 | 8 | Base condition row 166 |
| 104 Susanomon | 677 EmperorGreymon p2 + 678 MagnaGarurumon p11 | 8 | Base condition row 92 |
| 604 GraceNovamon | 173 Apollomon p3 + 733 Dianamon p15 | 8 | Base condition row 344 |
| 772 Chaosmon | 771 Darkdramon p2 + 49 BanchoLeomon p3 | 8 | Base condition row 439 |
| 118 Chaosmon: Valdur Arm | 49 BanchoLeomon p3 + 117 Varodurumon p10 | 8 | Base condition row 103 |
| 691 / chr691 Omnimon Alter-S | 689 BlitzGreymon p2 + 690 CresGarurumon p2 | 8 | DLC01 condition row 4 |

The `chr691` / Omnimon Alter-S pattern has two source edges in `evolution_to`, `689 -> 691` and `690 -> 691`, both with type `0`. Its `evolution_condition` row stores the two partners in columns 24/26/27/29 as `689, 2, 690, 2`.

Other official Jogress targets found in the local Base/DLC scan:

- 23 Dinobeemon: 91 Stingmon p7 + 365 ExVeemon p2
- 88 Omnimon: 27 WarGreymon p3 + 135 MetalGarurumon p11
- 230 Millenniummon: 385 Kimeramon p1 + 229 Machinedramon p11
- 408 Paildramon: 365 ExVeemon p2 + 91 Stingmon p7
- 494 Craniamon + Enbarrmon: 734 Craniamon p10 + 920 Enbarrmon p4
- 720 Silphymon: 15 Aquilamon p3 + 92 Gatomon p15
- 723 Shakkoumon: 711 Ankylomon p4 + 87 Angemon p10
- 748 Mastemon: 148 Angewomon p15 + 107 LadyDevimon p6
- 757 Omnimon Zwart: 175 BlackWarGreymon p11 + 182 MetalGarurumon (Black) p2
- 766 Alphamon: Ouryuken: 416 Alphamon p15 + 193 Owryumon p4

## Columns 11 and 12

The header source map still names `evolution_condition` columns 11 and 12 as `unknown_011` and `unknown_012`.

Observed local Base/DLC evidence:

- Every official Jogress / DNA row has column 11 = `0` and column 12 = `0`.
- Only two official condition rows found with nonzero column 11:
  - 390 Lucemon: column 11 = `30`, column 12 = `0`
  - 449 Parallelmon: column 11 = `40`, column 12 = `0`
- No official Base/DLC condition row found with nonzero column 12.

Current editor label: keep these as extra requirement fields and preserve/export them. Do not rename them to a gameplay term until we confirm the in-game meaning.
