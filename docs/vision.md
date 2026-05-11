# Food Delivery Platform — Vision

## Overview

A microservices-based food delivery platform allowing customers to browse restaurants, place orders, and track delivery status in real time. Modeled after services like Glovo and UberEats.

The system is built as an academic project demonstrating microservice architecture, fault tolerance, asynchronous communication, and distributed data management. Each service owns its own database, communicates over REST or Kafka, and is deployed via Docker Compose.

---

## Users

| Role       | Description                                                                 |
|------------|-----------------------------------------------------------------------------|
| Customer   | Browses restaurants and menus, places orders, tracks order status           |
| Restaurant | Manages menu items, views and confirms or rejects incoming orders           |
| Courier    | Receives delivery assignments from the routing service, updates delivery status |

All three roles authenticate through the same Auth Service and receive a JWT token scoped to their role. Role-based access is enforced at the API layer of each service.

---

## Core Capabilities

- **Authentication** — Registration, login, and logout with JWT tokens stored in Redis. Token invalidation on logout is enforced.
- **Restaurant catalog** — Browsing restaurants and menus stored in MongoDB. Catalog supports read operations under replica failure (read-only fallback).
- **Order management** — Full order lifecycle: `PENDING → CONFIRMED → PREPARING → READY_FOR_PICKUP → IN_DELIVERY → DELIVERED`. Order Service runs as two redundant instances behind a load balancer with shared session state in Redis.
- **Courier matching** — Graph-based assignment of the nearest available courier to a restaurant, modeled in Neo4j.
- **Async notifications** — Order status changes are published to a Kafka topic (`order-status-changed`). The Notification Service consumes events asynchronously. Messages are retained during consumer downtime and replayed on restart.

---

## Architecture Summary

| Service              | Language | Database         | Notes                                  |
|----------------------|----------|------------------|----------------------------------------|
| Auth Service         | Python   | PostgreSQL        | JWT tokens stored in Redis              |
| Order Service        | Python   | PostgreSQL        | 2 instances, Redis for shared state     |
| Restaurant Service   | Python   | MongoDB           | 3-node replica set                      |
| Routing Service      | Python   | Neo4j             | Graph-based courier matching            |
| Notification Service | Python   | —                 | Kafka consumer, logs to stdout          |

All services are exposed through a single Nginx API Gateway on port 80. Inter-service communication uses REST over the internal Docker network.

---

## Out of Scope

The following are explicitly excluded to keep the project focused and deliverable within the timeline.

| Topic                    | Reason excluded                                                  |
|--------------------------|------------------------------------------------------------------|
| Payment processing       | Orders are assumed pre-paid; no payment gateway integration      |
| Real geolocation / GPS   | Courier matching uses graph proximity in Neo4j, not live GPS     |
| Mobile native clients    | Web REST API only; no iOS or Android client                      |
| Admin panel              | No management UI for platform operators                          |
| Email / SMS notifications| Kafka consumer logs events to console only                       |
| Order history / analytics| Read queries only; no reporting or aggregation layer             |
| Multi-language support   | English only                                                     |

---

## Non-Functional Requirements

- **Fault tolerance — Order Service:** Two running instances behind Nginx. Killing one instance must not interrupt service; Redis preserves session state across the failover.
- **Fault tolerance — MongoDB:** Replica set of 3 nodes. Loss of the primary triggers automatic re-election. Loss of quorum forces the cluster into read-only mode — writes are rejected, reads continue.
- **Message durability — Kafka:** Messages published to `order-status-changed` are retained when the Notification Service is offline. All pending messages are processed in order when the consumer restarts.
- **Authentication integrity:** A JWT token must be rejected immediately after logout. Token state is the Redis record, not the token signature alone.

---

## Repository Structure

```
food-delivery/
├── services/
│   ├── auth-service/
│   ├── order-service/
│   ├── restaurant-service/
│   ├── routing-service/
│   └── notification-service/
├── api-gateway/
│   └── nginx.conf
├── docker/
│   ├── Dockerfile.auth
    ├── Dockerfile.notification
    ├── Dockerfile.order
    ├── Dockerfile.restaurant
    ├── Dockerfile.routing
    ├── kafka-init.sh
    └── mongo-init.sh
├── docker-compose.yml
├── .github/
│   └── workflows/
│       
└── docs/
    ├── vision.md               ← this file
    ├── use-cases.md
    ├── architecture-diagram.png
    ├── e2e-test.md
    └── failover-test.md
```