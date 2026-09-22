# Smart Network Monitoring System for Cloud Environments

An adaptive cloud-based system that monitors session-level network conditions, predicts network instability using machine learning, and dynamically adjusts application execution strategies to improve reliability under degraded connectivity.

## Overview

Modern cloud applications depend heavily on continuous client-server communication. When network conditions become unstable due to high latency, packet loss, congestion, or intermittent connectivity, repeated request failures and retries can increase execution time, communication overhead, and server load.

This project introduces an **Adaptive Middleware-based approach** that monitors network telemetry at the session level and uses a trained machine learning model to predict network conditions.

Based on the predicted network state, the system dynamically changes its execution strategy to reduce unnecessary communication and improve task reliability.

### Core Idea

Client
   ↓
Network Monitoring
   ↓
ML Prediction Engine
   ↓
Network State Classification
   ↓
Adaptive Execution Engine
   ↓
Optimized Requests
   ↓
Cloud Server
