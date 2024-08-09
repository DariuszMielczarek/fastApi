from datetime import datetime

from pydantic import BaseModel, Field


class OrderDTO(BaseModel):
    description: str
    time: int = Field(default=60, title="Estimated progress time", gt=0, lt=100)
    timestamp: datetime = Field(default=datetime.now())

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Order number 1",
                    "time": 15,
                },
                {
                    "description": "Order number 2",
                },
                {
                    "description": "Order number 3",
                    "timestamp": "2024-08-08T16:11:00.402291",
                    "time": 33
                }
            ]
        }
    }
