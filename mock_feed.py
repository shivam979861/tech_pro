"""Simulated social media feed of geo-tagged posts for TransitPulse."""

import asyncio
import logging
import random
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

MOCK_POSTS: list[dict[str, str]] = [
    # --- On-route hazards ---
    {
        "location_zone": "Silk Board Junction",
        "text": "Waist-deep water under the Silk Board flyover, traffic at standstill. Avoid if possible!",
    },
    {
        "location_zone": "Koramangala",
        "text": "Major accident near Sony World Junction, two buses collided. Ambulances on scene.",
    },
    {
        "location_zone": "HSR Layout",
        "text": "Huge tree fell on the main road near 27th Main. Entire lane blocked for hours.",
    },
    {
        "location_zone": "BTM Layout",
        "text": "Gas leak reported near BTM water tank. Fire brigade evacuating the area.",
    },
    {
        "location_zone": "Electronic City",
        "text": "Massive protest blocking the Electronic City flyover entrance. Hundreds gathered.",
    },
    {
        "location_zone": "Silk Board Junction",
        "text": "Another accident at Silk Board signal, auto rickshaw overturned. Expect delays.",
    },
    # --- On-route non-hazards ---
    {
        "location_zone": "Koramangala",
        "text": "Roads are pretty clear today near Forum Mall, smooth sailing!",
    },
    {
        "location_zone": "HSR Layout",
        "text": "Slight drizzle in HSR but traffic is moving fine. No issues.",
    },
    # --- Off-route hazards ---
    {
        "location_zone": "Whitefield",
        "text": "Massive flooding near Whitefield railway station. Water entering shops.",
    },
    {
        "location_zone": "Indiranagar",
        "text": "Fire broke out in a warehouse on 100 Feet Road, thick smoke everywhere.",
    },
    # --- Off-route non-hazards ---
    {
        "location_zone": "Jayanagar",
        "text": "Beautiful morning in Jayanagar, roads freshly paved. Great commute today.",
    },
    {
        "location_zone": "MG Road",
        "text": "Minor slowdown near MG Road metro station due to construction, nothing major.",
    },
]


async def stream_feed(
    callback: Callable[[dict[str, str]], Coroutine[Any, Any, None]],
) -> None:
    """Continuously loop mock posts with randomized delays, invoking callback for each."""
    round_num = 0
    while True:
        round_num += 1
        posts = MOCK_POSTS.copy()
        random.shuffle(posts)
        logger.info("Feed round %d starting — %d posts", round_num, len(posts))
        for post in posts:
            delay = random.uniform(2.0, 4.0)
            await asyncio.sleep(delay)
            logger.info("Feed post from %s: %s", post["location_zone"], post["text"][:60])
            await callback(post)
        logger.info("Feed round %d complete — pausing before next round", round_num)
        await asyncio.sleep(5.0)
