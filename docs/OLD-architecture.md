# NutriX Architecture

## 1. Intricate Architectural Blueprint

This diagram maps out the microservices boundaries, the structural network ports, database synchronization, and how the **Human-in-the-Loop (HITL)** retraining engine hooks into your storage layers.


```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                CLIENT / EDGE LAYER                               │
│                                                                                  │
│    ┌──────────────────────────────────┐        ┌────────────────────────────┐    │
│    │     ESP32-S3 PHYSICAL SCALE     │        │     FLUTTER MOBILE APP     │    │
│    │  [Load Cell]  [HX711] [Camera]  │        │  [UI Charts] [Search Bar]  │    │
│    └─────────────────┬────────────────┘        └─────────────┬──────────────┘    │
└──────────────────────┼───────────────────────────────────────┼───────────────────┘
                       │ (HTTP POST / Multipart)               │ (HTTP GET/POST)
                       ▼                                       ▼

┌──────────────────────────────────────────────────────────────────────────────────┐
│                    API GATEWAY (FastAPI Reverse Proxy)                          │
│ • Acts as a single entry point facing the public internet                       │
│ • Routes path requests:                                                         │
│   /v1/ingest -> Ingestion Svc                                                   │
│   /v1/user -> Analytics Svc                                                     │
└──────────────────────┬───────────────────────────────────────┬───────────────────┘
                       │                                       │
      ┌────────────────┴────────────────┐                      │
      ▼ (Commands / Heavy Compute)      │                      ▼ (Queries / Fast Reads)

┌──────────────────────────────────────┐│            ┌─────────────────────────────────────┐
│    INGESTION & INFERENCE SERVICE     ││            │       USER ANALYTICS SERVICE        │
├──────────────────────────────────────┤│            ├─────────────────────────────────────┤
│ • Decodes Barcodes (OpenCV)          ││            │ • Serves Timestamped History Logs   │
│ • Executes YOLOv8 Object Detection   ││            │ • Evaluates Category Alternatives   │
│ • Manages Unidentified Images        ││            │ • Coordinates Dietitian Target Plans│
└──────────────────┬───────────────────┘│            └──────────────────┬──────────────────┘
                   │                    │                               ▲
  ┌────────────────┴────────────────┐   │                               │
  ▼                                 ▼   │ (Direct Internal Proxy)       │

┌────────────────────┐   ┌───────────┐  │                               │
│ Local Dataset Disk │   │ Gemini Adpt│ │                               │
│ /dataset/pending   │   ├───────────┤  │                               │
│ /dataset/trained   │   │ [CB REQ]  │  │                               │
└────────────────────┘   └─────┬─────┘  │                               │
                               │        ▼                               │

                        ┌──────▼────────────────────────────────────────┼───┐
                        │               DATA STORAGE LAYER              │   │
                        │                                               │   │
                        │  ┌────────────────────────┐                   │   │
                        │  │ WRITE: PostgreSQL      │                   │   │
                        │  │ • Core Master Library  │                   │   │
                        │  │ • User Accounts        │                   │   │
                        │  └───────────┬────────────┘                   │   │
                        │              │ (Async Sync / Trigger)         │   │
                        │              ▼                                │   │
                        │  ┌────────────────────────┐                   │   │
                        │  │ READ: Redis Cache      │───────────────────┘   │
                        │  │ • Live Active Sessions │                       │
                        │  │ • Instant Daily Totals │                       │
                        │  └────────────────────────┘                       │
                        └───────────────────────────────────────────────────┘
```

---

# 2. Deep Dive Into the Core Components

## A. The Edge Tier (ESP32-S3 Network Node)

The physical scale doesn't run your database or AI model; it acts as an intelligent sensor collector.

### The Scale Logic

- Polls the 24-bit HX711 analog-to-digital converter continuously.
- Once the standard deviation of weight variations drops below `0.5g`
  for a sustained window of `500ms`, it flags the state as `STABLE`.

### The Network Payload & Device Identity

The ESP32:

1. Turns on the camera.
2. Captures an image frame buffer.
3. Wraps the following into an HTTP Multipart Form-Data request:
   - The stable weight value
   - The image payload
   - A hardcoded `Device-Token` (for basic device authentication)
   - A hardcoded `User-ID` (to link the scale to a specific user during the capstone phase)
4. Sends the request directly to the API Gateway.

---

## B. The API Gateway (The Structural Front Door)

Instead of exposing backend services directly to the internet,
everything is routed through a centralized API Gateway.

### Responsibilities

- Validates incoming requests
- Handles authentication tokens (e.g., verifying the scale's hardcoded `Device-Token`)
- Routes requests internally

### Example Routing

```http
POST /v1/ingest/weight-frame
```

Forwarded to:

```text
Ingestion & Inference Service
```

---

```http
GET /v1/user/daily-summary
```

Forwarded to:

```text
User Analytics Service
```

---

## C. Ingestion & Inference Service (Write Command Pipeline)

This service handles heavy-compute transactional tasks.

### Characteristics

- Stateless
- Horizontally scalable
- Optimized for AI workloads

### 1. Computer Vision Routing

When a food image arrives:

1. Image data is extracted
2. Passed into local YOLOv8 model
3. Object detection executes via Python runtime

### 2. Confidence Management

#### High Confidence (>= 80%)

- Automatically matched to PostgreSQL food library
- Example:

```text
White Bread
```

#### Low Confidence (< 80%)

- Item labeled as:

```text
unidentified_item
```

- Raw image stored in:

```text
/dataset/pending/
```

- Flutter app notified for manual review

---

## D. User Analytics & Query Service (Read Query Pipeline)

This service is isolated from ingestion workloads using:

```text
CQRS (Command Query Responsibility Segregation)
```

### Why Separate Read and Write Pipelines?

Heavy operations such as:

- YOLOv8 inference
- Gemini API requests
- Image processing

can block threads and slow down UI requests.

### Solution

The Analytics Service:

- Reads only from Redis
- Delivers instant responses
- Keeps mobile UI latency under:

```text
10ms
```

---

# 3. Circuit Breaking (Failure Protection Mode)

When a food item is not present inside the local SQL database,
the system queries the Gemini API for live nutrition data.

Since external APIs may fail, the system implements a:

```text
Circuit Breaker Pattern
```

---

## Circuit Breaker States

### 1. Closed State (Normal Operation)

- Requests flow normally to Gemini API
- Transactions succeed

---

### 2. Failure Trigger

If:

- Internet drops
- Gemini rate limits requests
- Timeouts occur
- HTTP 500 responses appear

then failures begin accumulating.

---

### 3. Open State (Safety Mode)

After:

```text
5 consecutive failures
```

the circuit trips open.

System behavior:

- Stops sending Gemini requests
- Prevents thread exhaustion
- Returns fallback response:

```text
"Remote nutrition search engine offline.
Defaulting to local temporary placeholder data."
```

---

### 4. Half-Open State (Recovery Check)

After cooldown period:

```text
60 seconds
```

a single trial request is allowed.

If successful:

```text
Circuit closes again
```

Otherwise:

```text
Circuit reopens immediately
```

---

# 4. Data Tracking Synchronization Loop (CQRS Setup)

This synchronization pipeline keeps calorie totals updating in real time.


```text
┌─────────────────────────────────┐
│ 1. INGESTION SERVICE (Write)    │
│ Saves item detail record into   │
│ PostgreSQL database.            │
└────────────────┬────────────────┘
                 │
                 ▼

┌─────────────────────────────────┐
│ 2. SQL COMPUTE TRIGGER          │
│ Calculates current running      │
│ calorie total for user.         │
└────────────────┬────────────────┘
                 │
                 ▼

┌─────────────────────────────────┐
│ 3. REDIS INSTANT SYNC           │
│ Pushes calculated total directly│
│ into Redis cache memory.        │
└────────────────┬────────────────┘
                 │
                 ▼

┌─────────────────────────────────┐
│ 4. SCALE DEVICE UPDATE          │
│ Gateway fetches Redis data      │
│ and updates scale LCD display.  │
└─────────────────────────────────┘
```

---

## Why PostgreSQL + Redis?

### PostgreSQL

Handles:

- Relational integrity
- User records
- Timestamps
- Exact nutritional metrics

### Redis

Handles:

- High-speed reads
- Live calorie totals
- Active sessions
- Real-time UI updates

Example Redis key:

```text
user_101_cal_total: 420
```

This hybrid architecture ensures both:

- Reliability
- Real-time performance

---

# 5. Workflows


## 1. Known Ingredient Flow (Fully Autonomous)

### Action

User places a known ingredient on the scale.

### Process

```text
Scale (Weight + Pic)
    ↓
Gateway
    ↓
Ingestion Service
    ↓
YOLOv8 recognizes item (>80%)
    ↓
Fetch macros from PostgreSQL
    ↓
Update Redis cache
    ↓
Scale LCD displays cumulative calories
```

---

## 2. Visually Unidentified but Library-Known Flow

### Action

AI misses the ingredient visually, but it exists in the app library.

### Process

```text
YOLOv8 fails (<80%)
    ↓
Image saved to /dataset/pending/
    ↓
App prompts user
    ↓
User selects ingredient manually
    ↓
Backend calculates weight delta
    ↓
Library density lookup
    ↓
Redis updated
    ↓
LCD updates
    ↓
Image moved into training dataset
```

---

## 3. Completely Unknown Ingredient Flow (Gemini / Manual)

### Action

User introduces a food item unknown to both AI and local database.

### Process

```text
YOLOv8 fails
    ↓
App search fails
    ↓
User triggers Gemini Search
    ↓
Gemini converts data into structured JSON
    ↓
New item stored in PostgreSQL
    ↓
Backend updates Redis calorie totals
    ↓
Scale LCD updates instantly
```