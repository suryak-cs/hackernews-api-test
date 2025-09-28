# hackernews-api-test
This project contains tests for the HackerNews API using pytest, requests, and aiohttp.


## Prerequisites
- Python 3.6 or higher
- Git

## Installation and Setup
1. Clone the repository:
```bash
git clone https://github.com/suryak-cs/hackernews-api-test.git
```

2. Navigate to the project directory:
```bash
cd hackernews-api-test
```

3. Create a virtual environment:
```bash
python3 -m venv myvenv
```

4. Activate the virtual environment:
```bash
source myvenv/bin/activate
```

5. Install the required dependencies:
```bash
pip install pytest requests pytest-mock aiohttp pytest-asyncio
```

## Running Tests

To run the tests with verbose output and standard output capture disabled, use the following command:

```bash
pytest test_hacker_news.py -v -s
```

## Tests
### Acceptance Tests
- `test_top_stories` - Tests the Top Stories API
- `test_top_story_from_stories` - Tests Items API by using the top story from Top Stories API
- `test_top_comment_from_top_story_in_top_stories` - Tests top comments of the top story by using Items API
- `test_total_comment_count` - Tests the total comments(recursively) against the total descendants
### Edge Cases via Mocked tests
- `test_top_stories_empty_response` - Tests graceful handling when empty response
- `test_top_story_non_existent_id` - Tests the application handles the missing story gracefully.
- `test_top_story_missing_id` - Tests the application detects and handles the missing/mandatory field.
## Notes

- Ensure the virtual environment is activated before running tests.
- The tests in `test_hacker_news.py` cover the HackerNews API functionality using both synchronous (requests) and asynchronous (aiohttp) approaches.
- Error has been detected in `test_total_comment_count` while tallying the descendants with the total comments found recursively. This may be due to dead comments. Subject to discussion.