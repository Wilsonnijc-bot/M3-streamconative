# First Clip Memory Construction: Gemini 3.8 vs Qwen 3.5 4B

## Shared preprocessing

| Stage | Latency ms |
| --- | ---: |
| Clip decode | 2928.43 |
| Deepgram ASR | 236.79 |
| MAI-Transcribe-2 ASR | 1063.40 |
| ASR total | 1300.20 |
| Audio segmentation | 3.47 |
| CAM++ speech embedding | 1140.64 |
| Buffalo-L detection + recognition | 9044.04 |
| Face clustering | 4.19 |
| VLM context construction | 4033.64 |
| Shared preprocessing wall time | 18545.20 |

## Branch comparison

Text embeddings: OpenRouter `openai/text-embedding-3-large` via `/api/v1/embeddings`.

| Model | VLM ms | Text embed ms | Insert ms | Equivalence ms | Graph total ms | Branch ms | Clip-to-graph ms | Nodes | Edges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3.5-4b | 111703.85 | 1059.59 | 0.11 | 0.05 | 0.16 | 112763.80 | 131310.04 | 10 | 0 |
| gemini-3.8-flash | 12124.97 | 1666.47 | 0.38 | 0.09 | 0.47 | 13792.45 | 32339.18 | 10 | 3 |

## qwen3.5-4b memory

### Raw VLM response

```json
{
	"video_description": [
		"A first-person perspective video shows a person walking into a room where a group of people are seated around a table covered with a checkered tablecloth.",
		"The person holding the camera approaches the table and holds up a smartphone towards the group.",
		"The smartphone screen displays a stopwatch application with a countdown timer.",
		"The timer counts down from 30.00 seconds while the group members look at the phone and the camera holder.",
		"The person holding the phone interacts with the device, likely starting or managing the timer for the group."
	],
	"high_level_conclusions": [
		"The group of people appears to be participating in a timed activity or challenge.",
		"The person holding the smartphone is acting as the facilitator or organizer, managing the timing of the event.",
		"The voice instructions suggest a focus on timing and timestamps, reinforcing the idea of a structured timed task."
	]
}
```

### Video descriptions

- A first-person perspective video shows a person walking into a room where a group of people are seated around a table covered with a checkered tablecloth.
- The person holding the camera approaches the table and holds up a smartphone towards the group.
- The smartphone screen displays a stopwatch application with a countdown timer.
- The timer counts down from 30.00 seconds while the group members look at the phone and the camera holder.
- The person holding the phone interacts with the device, likely starting or managing the timer for the group.

### High-level conclusions

- The group of people appears to be participating in a timed activity or challenge.
- The person holding the smartphone is acting as the facilitator or organizer, managing the timing of the event.
- The voice instructions suggest a focus on timing and timestamps, reinforcing the idea of a structured timed task.

### Graph delta

```json
{
  "nodes_added": 10,
  "edges_added": 0,
  "nodes": [
    {
      "id": 0,
      "type": "voice",
      "metadata": {
        "contents": [
          "MAI: 好，然后一个秒表。",
          "MAI: 对，戳一下。"
        ]
      },
      "embedding_count": 2,
      "embedding_dimensions": [
        192,
        192
      ]
    },
    {
      "id": 1,
      "type": "voice",
      "metadata": {
        "contents": [
          "MAI: 时间戳。"
        ]
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        192
      ]
    },
    {
      "id": 2,
      "type": "episodic",
      "metadata": {
        "contents": [
          "A first-person perspective video shows a person walking into a room where a group of people are seated around a table covered with a checkered tablecloth."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 3,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The person holding the camera approaches the table and holds up a smartphone towards the group."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 4,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The smartphone screen displays a stopwatch application with a countdown timer."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 5,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The timer counts down from 30.00 seconds while the group members look at the phone and the camera holder."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 6,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The person holding the phone interacts with the device, likely starting or managing the timer for the group."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 7,
      "type": "semantic",
      "metadata": {
        "contents": [
          "The group of people appears to be participating in a timed activity or challenge."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 8,
      "type": "semantic",
      "metadata": {
        "contents": [
          "The person holding the smartphone is acting as the facilitator or organizer, managing the timing of the event."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 9,
      "type": "semantic",
      "metadata": {
        "contents": [
          "The voice instructions suggest a focus on timing and timestamps, reinforcing the idea of a structured timed task."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    }
  ],
  "edges": []
}
```

### Actual nodes

```json
[
  {
    "id": 0,
    "type": "voice",
    "metadata": {
      "contents": [
        "MAI: 好，然后一个秒表。",
        "MAI: 对，戳一下。"
      ]
    },
    "embedding_count": 2,
    "embedding_dimensions": [
      192,
      192
    ]
  },
  {
    "id": 1,
    "type": "voice",
    "metadata": {
      "contents": [
        "MAI: 时间戳。"
      ]
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      192
    ]
  },
  {
    "id": 2,
    "type": "episodic",
    "metadata": {
      "contents": [
        "A first-person perspective video shows a person walking into a room where a group of people are seated around a table covered with a checkered tablecloth."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 3,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The person holding the camera approaches the table and holds up a smartphone towards the group."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 4,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The smartphone screen displays a stopwatch application with a countdown timer."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 5,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The timer counts down from 30.00 seconds while the group members look at the phone and the camera holder."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 6,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The person holding the phone interacts with the device, likely starting or managing the timer for the group."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 7,
    "type": "semantic",
    "metadata": {
      "contents": [
        "The group of people appears to be participating in a timed activity or challenge."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 8,
    "type": "semantic",
    "metadata": {
      "contents": [
        "The person holding the smartphone is acting as the facilitator or organizer, managing the timing of the event."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 9,
    "type": "semantic",
    "metadata": {
      "contents": [
        "The voice instructions suggest a focus on timing and timestamps, reinforcing the idea of a structured timed task."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  }
]
```

### Actual edges

```json
[]
```

## gemini-3.8-flash memory

### Raw VLM response

```json
{
  "video_description": [
    "The camera wearer holds a smartphone facing a group seated around a table.",
    "The camera wearer navigates the phone interface to open the stopwatch tool.",
    "Several participants sit around the table with equipment cases and items laid out.",
    "<voice_0> instructs to prepare a stopwatch.",
    "<voice_1> mentions a timestamp.",
    "The camera wearer activates the stopwatch display on the smartphone."
  ],
  "high_level_conclusions": [
    "The camera wearer is syncing timestamps across devices for an upcoming recording session.",
    "<voice_0> is actively directing or coordinating the preparation procedure."
  ]
}
```

### Video descriptions

- The camera wearer holds a smartphone facing a group seated around a table.
- The camera wearer navigates the phone interface to open the stopwatch tool.
- Several participants sit around the table with equipment cases and items laid out.
- <voice_0> instructs to prepare a stopwatch.
- <voice_1> mentions a timestamp.
- The camera wearer activates the stopwatch display on the smartphone.

### High-level conclusions

- The camera wearer is syncing timestamps across devices for an upcoming recording session.
- <voice_0> is actively directing or coordinating the preparation procedure.

### Graph delta

```json
{
  "nodes_added": 10,
  "edges_added": 3,
  "nodes": [
    {
      "id": 0,
      "type": "voice",
      "metadata": {
        "contents": [
          "MAI: 好，然后一个秒表。",
          "MAI: 对，戳一下。"
        ]
      },
      "embedding_count": 2,
      "embedding_dimensions": [
        192,
        192
      ]
    },
    {
      "id": 1,
      "type": "voice",
      "metadata": {
        "contents": [
          "MAI: 时间戳。"
        ]
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        192
      ]
    },
    {
      "id": 2,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The camera wearer holds a smartphone facing a group seated around a table."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 3,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The camera wearer navigates the phone interface to open the stopwatch tool."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 4,
      "type": "episodic",
      "metadata": {
        "contents": [
          "Several participants sit around the table with equipment cases and items laid out."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 5,
      "type": "episodic",
      "metadata": {
        "contents": [
          "<voice_0> instructs to prepare a stopwatch."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 6,
      "type": "episodic",
      "metadata": {
        "contents": [
          "<voice_1> mentions a timestamp."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 7,
      "type": "episodic",
      "metadata": {
        "contents": [
          "The camera wearer activates the stopwatch display on the smartphone."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 8,
      "type": "semantic",
      "metadata": {
        "contents": [
          "The camera wearer is syncing timestamps across devices for an upcoming recording session."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 9,
      "type": "semantic",
      "metadata": {
        "contents": [
          "<voice_0> is actively directing or coordinating the preparation procedure."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    }
  ],
  "edges": [
    {
      "source": 0,
      "target": 5,
      "weight": 1.0,
      "source_type": "voice",
      "target_type": "episodic"
    },
    {
      "source": 0,
      "target": 9,
      "weight": 1.0,
      "source_type": "voice",
      "target_type": "semantic"
    },
    {
      "source": 1,
      "target": 6,
      "weight": 1.0,
      "source_type": "voice",
      "target_type": "episodic"
    }
  ]
}
```

### Actual nodes

```json
[
  {
    "id": 0,
    "type": "voice",
    "metadata": {
      "contents": [
        "MAI: 好，然后一个秒表。",
        "MAI: 对，戳一下。"
      ]
    },
    "embedding_count": 2,
    "embedding_dimensions": [
      192,
      192
    ]
  },
  {
    "id": 1,
    "type": "voice",
    "metadata": {
      "contents": [
        "MAI: 时间戳。"
      ]
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      192
    ]
  },
  {
    "id": 2,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The camera wearer holds a smartphone facing a group seated around a table."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 3,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The camera wearer navigates the phone interface to open the stopwatch tool."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 4,
    "type": "episodic",
    "metadata": {
      "contents": [
        "Several participants sit around the table with equipment cases and items laid out."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 5,
    "type": "episodic",
    "metadata": {
      "contents": [
        "<voice_0> instructs to prepare a stopwatch."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 6,
    "type": "episodic",
    "metadata": {
      "contents": [
        "<voice_1> mentions a timestamp."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 7,
    "type": "episodic",
    "metadata": {
      "contents": [
        "The camera wearer activates the stopwatch display on the smartphone."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 8,
    "type": "semantic",
    "metadata": {
      "contents": [
        "The camera wearer is syncing timestamps across devices for an upcoming recording session."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 9,
    "type": "semantic",
    "metadata": {
      "contents": [
        "<voice_0> is actively directing or coordinating the preparation procedure."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  }
]
```

### Actual edges

```json
[
  {
    "source": 0,
    "target": 5,
    "weight": 1.0,
    "source_type": "voice",
    "target_type": "episodic"
  },
  {
    "source": 0,
    "target": 9,
    "weight": 1.0,
    "source_type": "voice",
    "target_type": "semantic"
  },
  {
    "source": 1,
    "target": 6,
    "weight": 1.0,
    "source_type": "voice",
    "target_type": "episodic"
  }
]
```
