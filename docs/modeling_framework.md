# Modeling Framework

## Overview

This repository is built around a simple hierarchy:

1. **Fundamental valuation forms the call**
2. **Probabilistic tools validate the call**
3. **Technical models help describe the path, not the destination**

That hierarchy is intentional and should be preserved in any presentation of the work.

## DCF as the Core Research Engine

The discounted cash flow framework is the primary model in the project. It converts the structured operating case into an intrinsic value per share by combining:

- revenue growth assumptions
- profitability assumptions
- reinvestment assumptions
- capital structure inputs
- discount rate
- terminal growth

The output of this layer is the official target price used throughout the repository.

## Monte Carlo as Probabilistic Validation

The Monte Carlo engine does not define the official target price. Instead, it tests whether the valuation remains coherent under stochastic variation in the main inputs.

The key interpretation is:

- if the center of the distribution converges to the same neighborhood as the base DCF,
- then the valuation is not just a single-point opinion,
- it is part of a robust distribution of plausible fair values.

## Standalone LSTM as a Diagnostic Tool

The standalone LSTM should be interpreted as a methodological benchmark. It tests whether a pure technical model, trained on price and technical indicators, can produce a strong enough standalone signal.

In this project, it should not be treated as a thesis-forming model.

## Hybrid Model as a Technical Overlay

The hybrid model is the most conceptually interesting part of the repository. It combines:

- a valuation-consistent anchor path
- a residual-return LSTM ensemble

This allows the model to estimate how price may evolve around the fundamental path without allowing the neural network to override the valuation framework itself.

## Official Interpretation

- **Target price:** fundamental output
- **Bear / Base / Bull:** structured scenario outputs
- **Monte Carlo:** robustness and dispersion
- **Standalone LSTM:** diagnostic and benchmark
- **Hybrid LSTM + valuation:** trajectory and timing overlay

This is the correct institutional interpretation of the repository.
