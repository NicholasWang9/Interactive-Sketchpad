import asyncio
import os
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

client = AsyncOpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)

CODE_INTERPRETER_TOOL = {
    "type": "code_interpreter",
    "container": {"type": "auto"}
}


async def main():
    print("Starting request...")

    t0 = time.time()

    resp = await client.responses.create(
        model="gpt-5.2",
        tools=[CODE_INTERPRETER_TOOL],
        input=(
            "Plot y=x^2 from x=-5 to x=5. "
            "Create exactly one matplotlib figure. "
            "Save exactly one PNG image."
        ),
    )

    elapsed = time.time() - t0

    print(f"\nResponses create took: {elapsed:.2f} seconds\n")

    if hasattr(resp, "output_text"):
        print("OUTPUT TEXT:")
        print(resp.output_text)

    print("\nOUTPUT TYPES:")
    for item in resp.output:
        print(item.type)

        if hasattr(item, "content"):
            for c in item.content:
                print("  ", c.type)


if __name__ == "__main__":
    asyncio.run(main())