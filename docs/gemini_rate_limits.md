# Gemini API Rate Limits Configuration

## Overview (Updated Rates)

The backend exclusively uses **Gemma 4 31B** and high-capacity Gemma models, completely avoiding restrictive `gemini-2.5-flash` limits.

### Gemma 4 31B (Primary)
- **RPM (Requests Per Minute):** 30 RPM
- **TPM (Tokens Per Minute):** 16K
- **RPD (Requests Per Day):** 14,400 (14.4K) RPD

### Gemma 4 26B (Fallback)
- Automatically activated if primary model encounters unexpected rate limits or failures.

## Model Configuration

- **Primary Model:** `gemma-4-31b-it`
- **Fallback Model:** `gemma-4-26b-a4b-it`
- **Model Interval:** `2.5` seconds (~24 RPM)
- **Global Daily Limit Guard:** `14,000` RPD

## Implementation Details

The `GeminiExtractor` class enforces these limits:

```python
self.request_interval = 4.0  # 15 RPM = 60s / 15 = 4s per request
self.daily_limit = 1000      # Conservative limit
```

### Automatic Fallback Logic

When a `429 RESOURCE_EXHAUSTED` error is detected:
1. Check current model
2. If using `gemini-2.5-flash-lite`, switch to `gemini-2.5-flash`
3. Retry request immediately with new model
4. Continue processing without interruption

## Daily Processing Capacity

With automatic model switching:
- **flash-lite quota:** 20 requests/day
- **flash quota:** 20 requests/day
- **Total capacity:** ~40 requests/day (with fallback)

## Best Practices

1. **Use Sequential Processing:** Process beers one-by-one to maximize brewery hint benefits
2. **Skip Already Enriched:** Only process beers without Gemini data
3. **Monitor Usage:** Check API console regularly
4. **Batch Processing:** Process in small batches (10-50 beers) to manage quotas
5. **Daily Resets:** Quotas reset at midnight UTC

## Upgrade Options

For higher throughput, consider upgrading to paid tier:
- **Pay-as-you-go:** Higher RPM and RPD limits
- **Enterprise:** Custom quotas and SLA

## Current Status

✅ **Automatic model switching implemented**  
✅ **Sequential enrichment working**  
⚠️ **flash-lite quota exhausted (34/20 used)**  
✅ **flash quota available (0/20 used)**  

**Recommendation:** Continue using `sequential_enrich.py` which will automatically use `gemini-2.5-flash` for remaining beers.
