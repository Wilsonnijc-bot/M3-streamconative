# First Clip Memory Construction: Gemini 3.8 vs Qwen 3.5 4B

## Shared preprocessing

| Stage | Latency ms |
| --- | ---: |
| Clip decode | 2268.80 |
| Deepgram ASR | 2658.19 |
| MAI-Transcribe-2 ASR | 8177.42 |
| ASR total | 10835.62 |
| Audio segmentation | 5.06 |
| CAM++ speech embedding | 977.72 |
| Buffalo-L detection + recognition | 3568.84 |
| Face clustering | 9.39 |
| VLM context construction | 3920.29 |
| Shared preprocessing wall time | 21720.25 |

## Branch comparison

Text embeddings: OpenRouter `openai/text-embedding-3-large` via `/api/v1/embeddings`.

| Model | VLM ms | Text embed ms | Insert ms | Equivalence ms | Graph total ms | Branch ms | Clip-to-graph ms | Nodes | Edges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3.5-4b | 107613.76 | 3834.57 | 0.14 | 0.04 | 0.18 | 111448.75 | 133169.57 | 11 | 0 |
| gemini-3.8-flash | 25485.34 | 4799.15 | 0.41 | 0.05 | 0.46 | 30285.46 | 52006.62 | 10 | 1 |

## qwen3.5-4b memory

### Raw VLM response

```json
{
	"video_description": [
		"A first-person perspective shows a person walking into a room where a group of people are sitting around a table.",
		"The person holding the camera approaches the table, which is covered with a checkered tablecloth and has various items on it.",
		"The person holds up a smartphone displaying a stopwatch application.",
		"The stopwatch on the phone screen counts down from 30 seconds.",
		"The group of people at the table watches the phone screen as the timer counts down.",
		"The person holding the phone lowers it after the countdown."
	],
	"high_level_conclusions": [
		"The group appears to be preparing for a timed activity or challenge involving VR headsets.",
		"The person holding the camera is acting as a facilitator or host, managing the timer for the group.",
		"The voice instructions suggest setting up a stopwatch and wearing a device, likely the VR headset seen on the table."
	]
}
```

### Video descriptions

- A first-person perspective shows a person walking into a room where a group of people are sitting around a table.
- The person holding the camera approaches the table, which is covered with a checkered tablecloth and has various items on it.
- The person holds up a smartphone displaying a stopwatch application.
- The stopwatch on the phone screen counts down from 30 seconds.
- The group of people at the table watches the phone screen as the timer counts down.
- The person holding the phone lowers it after the countdown.

### High-level conclusions

- The group appears to be preparing for a timed activity or challenge involving VR headsets.
- The person holding the camera is acting as a facilitator or host, managing the timer for the group.
- The voice instructions suggest setting up a stopwatch and wearing a device, likely the VR headset seen on the table.

### Graph delta

```json
{
  "nodes_added": 11,
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
          "A first-person perspective shows a person walking into a room where a group of people are sitting around a table."
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
          "The person holding the camera approaches the table, which is covered with a checkered tablecloth and has various items on it."
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
          "The person holds up a smartphone displaying a stopwatch application."
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
          "The stopwatch on the phone screen counts down from 30 seconds."
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
          "The group of people at the table watches the phone screen as the timer counts down."
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
          "The person holding the phone lowers it after the countdown."
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
          "The group appears to be preparing for a timed activity or challenge involving VR headsets."
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
          "The person holding the camera is acting as a facilitator or host, managing the timer for the group."
        ],
        "timestamp": 1
      },
      "embedding_count": 1,
      "embedding_dimensions": [
        3072
      ]
    },
    {
      "id": 10,
      "type": "semantic",
      "metadata": {
        "contents": [
          "The voice instructions suggest setting up a stopwatch and wearing a device, likely the VR headset seen on the table."
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
        "A first-person perspective shows a person walking into a room where a group of people are sitting around a table."
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
        "The person holding the camera approaches the table, which is covered with a checkered tablecloth and has various items on it."
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
        "The person holds up a smartphone displaying a stopwatch application."
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
        "The stopwatch on the phone screen counts down from 30 seconds."
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
        "The group of people at the table watches the phone screen as the timer counts down."
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
        "The person holding the phone lowers it after the countdown."
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
        "The group appears to be preparing for a timed activity or challenge involving VR headsets."
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
        "The person holding the camera is acting as a facilitator or host, managing the timer for the group."
      ],
      "timestamp": 1
    },
    "embedding_count": 1,
    "embedding_dimensions": [
      3072
    ]
  },
  {
    "id": 10,
    "type": "semantic",
    "metadata": {
      "contents": [
        "The voice instructions suggest setting up a stopwatch and wearing a device, likely the VR headset seen on the table."
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
		"A person holding a smartphone stands facing several individuals seated around a table.",
		"The phone holder navigates the smartphone screen to access the clock app.",
		"The participants around the table watch and converse among themselves.",
		"The phone holder switches to the stopwatch interface on the phone.",
		"The stopwatch timer on the phone screen is reset and activated."
	],
	"high_level_conclusions": [
		"The person holding the phone is setting up a stopwatch timer to record timestamps for synchronization or task timing.",
		"The group seated around the table is participating in a structured collaborative activity or experiment.",
		"<voice_0> provides instructions to set up the stopwatch and mark timestamps."
	]
}
```

### Video descriptions

- A person holding a smartphone stands facing several individuals seated around a table.
- The phone holder navigates the smartphone screen to access the clock app.
- The participants around the table watch and converse among themselves.
- The phone holder switches to the stopwatch interface on the phone.
- The stopwatch timer on the phone screen is reset and activated.

### High-level conclusions

- The person holding the phone is setting up a stopwatch timer to record timestamps for synchronization or task timing.
- The group seated around the table is participating in a structured collaborative activity or experiment.
- <voice_0> provides instructions to set up the stopwatch and mark timestamps.

### Graph delta

```json
{
  "nodes_added": 10,
  "edges_added": 1,
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
          "A person holding a smartphone stands facing several individuals seated around a table."
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
          "The phone holder navigates the smartphone screen to access the clock app."
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
          "The participants around the table watch and converse among themselves."
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
          "The phone holder switches to the stopwatch interface on the phone."
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
          "The stopwatch timer on the phone screen is reset and activated."
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
          "The person holding the phone is setting up a stopwatch timer to record timestamps for synchronization or task timing."
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
          "The group seated around the table is participating in a structured collaborative activity or experiment."
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
          "<voice_0> provides instructions to set up the stopwatch and mark timestamps."
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
      "target": 9,
      "weight": 1.0,
      "source_type": "voice",
      "target_type": "semantic"
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
        "A person holding a smartphone stands facing several individuals seated around a table."
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
        "The phone holder navigates the smartphone screen to access the clock app."
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
        "The participants around the table watch and converse among themselves."
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
        "The phone holder switches to the stopwatch interface on the phone."
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
        "The stopwatch timer on the phone screen is reset and activated."
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
        "The person holding the phone is setting up a stopwatch timer to record timestamps for synchronization or task timing."
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
        "The group seated around the table is participating in a structured collaborative activity or experiment."
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
        "<voice_0> provides instructions to set up the stopwatch and mark timestamps."
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
    "target": 9,
    "weight": 1.0,
    "source_type": "voice",
    "target_type": "semantic"
  }
]
```
