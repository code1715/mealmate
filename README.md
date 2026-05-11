# MealMate

[![CI](https://github.com/code1715/mealmate/actions/workflows/ci.yml/badge.svg)](https://github.com/code1715/mealmate/actions/workflows/ci.yml)

MealMate is a scalable, highly available food delivery platform designed to seamlessly connect customers, local restaurants, and couriers.

## Services

| Service | Description |
|---|---|
| `services/auth` | Authentication and authorisation |
| `services/order` | Order lifecycle management |
| `services/restaurant` | Restaurant catalogue and menu |
| `services/routing` | Courier routing and assignment |
| `services/notification` | Push / email / SMS notifications |
| `api-gateway` | Single entry point for all client traffic |

## Local Setup

```bash
git clone https://github.com/code1715/mealmate.git
cd mealmate
docker-compose up
```
