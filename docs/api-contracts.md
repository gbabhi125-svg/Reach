# REACH API reference

Auto-generated from the services' OpenAPI specs. Each running service also serves interactive docs at `/docs` (Swagger UI).


## pricing-service — http://localhost:8001  ([docs](http://localhost:8001/docs))

| Method | Path | Body fields |
|---|---|---|
| GET | `/categories` |  |
| GET | `/categories/{name}` |  |
| PATCH | `/categories/{name}` | `rate_per_kg`?, `quota_kg`? |

## generator-service — http://localhost:8002  ([docs](http://localhost:8002/docs))

| Method | Path | Body fields |
|---|---|---|
| POST | `/generators/request-otp` | `phone` |
| POST | `/generators/verify-otp` | `otp_session_id`, `code` |
| POST | `/postings` | `generator_id`, `geo_cluster_id`, `category_name`, `est_weight_kg` |
| GET | `/clusters/{cluster_id}/quota-progress` |  |
| POST | `/generators` | `name`, `phone`, `geo_cluster_id`, `otp_session_id` |
| POST | `/clusters` | `name`, `lat`?, `lng`? |

## collector-service — http://localhost:8003  ([docs](http://localhost:8003/docs))

| Method | Path | Body fields |
|---|---|---|
| POST | `/collectors/request-otp` | `phone` |
| POST | `/collectors/verify-otp` | `otp_session_id`, `code` |
| POST | `/collectors` | `name`, `phone`, `otp_session_id` |
| POST | `/collectors/{collector_id}/kyc/initiate` | `aadhaar_number` |
| POST | `/collectors/{collector_id}/kyc/verify` | `aadhaar_number`, `otp` |
| GET | `/runs/open` |  |
| POST | `/runs/{run_id}/accept` | `collector_id` |
| GET | `/runs/{run_id}/stops` |  |

## pickup-service — http://localhost:8004  ([docs](http://localhost:8004/docs))

| Method | Path | Body fields |
|---|---|---|
| POST | `/runs/{run_id}/pickups` | `posting_id`, `actual_weight_kg`, `photo_url`? |
| POST | `/runs/{run_id}/complete` |  |

## data-layer-service — http://localhost:8005  ([docs](http://localhost:8005/docs))

| Method | Path | Body fields |
|---|---|---|
| GET | `/reports/cluster/{cluster_id}` |  |
| GET | `/reports/region` |  |

## corporate-service — http://localhost:8006  ([docs](http://localhost:8006/docs))

| Method | Path | Body fields |
|---|---|---|
| POST | `/corporates` | `name`, `gstin`, `phone`, `geo_cluster_id` |
| POST | `/corporates/{corporate_id}/pickups` | `category_name`, `est_weight_kg` |
| GET | `/corporates/{corporate_id}/report` |  |

`?` = optional field.
