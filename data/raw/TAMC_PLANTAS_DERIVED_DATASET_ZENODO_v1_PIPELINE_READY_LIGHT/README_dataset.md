# TAMC-PLANTAS derived dataset

This Zenodo package is a derived, attribution-preserving and pipeline-ready dataset
created to support reproducible execution of the TAMC-PLANTAS analysis.

It is based on the public plant electrophysiology source-data package associated with:

Madariaga, D., Arro, D., Irarrázaval, C., Soto, A., Guerra, F., Romero, A.,
Ovalle, F., Fedrigolli, E., DesRosiers, T., Serbe-Kamp, É., & Marzullo, T.
(2024). A library of electrophysiological responses in plants – A model of
transversal education and open science. Plant Signaling & Behavior, 19(1),
2310977.

Associated article:
https://doi.org/10.1080/15592324.2024.2310977

Original source data:
https://figshare.com/s/65447c618656565467e6

Original license:
Creative Commons Attribution 4.0 International (CC BY 4.0)

## What this derived package contains

- data/raw_plants/: plant electrophysiology .wav recordings reorganized in a TAMC-PLANTAS-ready species-level structure.
- original_source/: copy of the original downloaded source ZIP, when available.
- manifests/files_manifest_sha256.csv: SHA-256 checksum manifest for traceability.
- manifests/species_index.csv: species-level file counts.
- manifests/dataset_provenance.json: machine-readable provenance metadata.
- docs/source_attribution.txt: attribution statement.
- docs/LICENSE_original_CC_BY_4.0.txt: original license note.

## Changes made

This is not the original source-data release. It is a derived dataset prepared for
reproducible TAMC-PLANTAS analysis. Changes include:

- reorganized recordings into a TAMC-PLANTAS species-level folder structure;
- added machine-readable manifests;
- added SHA-256 checksums;
- added processing/provenance metadata;
- prepared the package for reproducible pipeline execution.

## How to use with TAMC-PLANTAS

Place the raw_plants/ folder under:

TAMC-PLANTAS/data/raw_plants/

Then run:

python run_plantasfull.py

or the non-interactive launcher:

python run_plantasfull_sin_pausas.py

## Required citation

Users of this package should cite both:

1. The original source data and associated article by Madariaga et al. (2024).
2. The TAMC-PLANTAS derived Zenodo package.
