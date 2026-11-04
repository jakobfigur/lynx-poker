# Model starter pack

## Purpose

These checkpoints support reproduction and exploration of the Lynx research project. Intended environments are the local simulator, PokerTH play-money games and documented research benchmarks. They are not intended for real-money poker, autonomous betting or consequential decisions.

## Contents and provenance

The repository includes small policy checkpoints for the `pros-*`, `lynx-*` and `human-1` generations, plus a human-style fold model. [Data and licensing](DATEN-UND-LIZENZEN.md) lists every included file, its role and the third-party data sources. Training and evaluation methods and dated results are in the [case study](CASE-STUDY.md).

Training sources include Pluribus hands distributed through the PHH dataset, simulator-generated play and historical HandHQ-derived decisions. The underlying population and poker formats are narrow; performance should not be generalized to other players, stakes, clients or game distributions. The original HandHQ terms have not been independently reviewed; no raw hand histories are distributed here.

## Evaluation and limitations

Historical results are reported with their sample sizes and uncertainty where available. Passing the software test suite does not reproduce those experiments. The package does not establish profitability, general strategic optimality or performance against present-day human players. Large training datasets, raw recordings and some optional value networks are not included in the Git tree.

## Loading and integrity

Only load checkpoints whose source you trust. PyTorch model formats can carry executable serialization payloads. This repository's release process records SHA-256 checksums for included model files; compare separately downloaded assets with the release checksums before use. Checksums establish file identity, not model quality or legal clearance.

## License

The project distributes its starter pack under the accompanying MIT license, as described in the data document. Third-party sources retain their own terms. This card documents provenance and limitations; it does not provide a legal determination about third-party rights.
