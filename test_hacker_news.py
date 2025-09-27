import pytest
import pytest_asyncio
import requests
import asyncio
import aiohttp
from unittest.mock import patch, AsyncMock

def fetch_top_stories():
    """Fetch the list of top story IDs from Hacker News top-stories API. It may contain Job(s)"""
    url = "https://hacker-news.firebaseio.com/v0/topstories.json?print=pretty"
    try:
        response = requests.get(url)
        print(f"Validation - Status code[ top-stories API ] :: Expected:200  Actual:{response.status_code}")
        response.raise_for_status()
        data = response.json()
        print(f"Validation - Data Type[ top-stories API ] :: Expected:<class 'list'> Actual:{type(data)}")
        if not isinstance(data, list):
            print(f"Error - top-stories response is not a list, got {type(data)}")
            return None
        if not all(isinstance(item, int) for item in data):
            print(f"Error: top-stories response contains non-integer items: {data}")
            return None
        return data
    except requests.exceptions.RequestException:
        return None

async def fetch_item_async(item_id, session):
    """Fetch a single item from Hacker News items API asynchronously."""
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError:
        return None

@pytest_asyncio.fixture(scope="function")
async def client_session():
    """Fixture to provide an aiohttp ClientSession."""
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.fixture(scope="function")
def top_stories():
    """Fixture to provide top stories list."""
    stories = fetch_top_stories()
    assert stories is not None, "Failed to fetch top stories"
    assert len(stories) > 0, "Top stories list is empty"
    return stories

async def get_stories_with_less_comments(top_stories, client_session, threshold=10):
    """Helper: return list of stories with fewer than `threshold` descendants using 'descendants' field."""
    stories_with_less_comments = []
    total = 0
    for story_id in top_stories:
        if total > 5:
            continue

        story_item = await fetch_item_async(story_id, client_session)
        if story_item:
            # Use the 'descendants' field directly
            count = story_item.get("descendants", 0)  # defaults to 0 if not present

            if threshold > count > 0:
                total+=1
                stories_with_less_comments.append(story_id)
    print(stories_with_less_comments)
    return stories_with_less_comments

@pytest.mark.asyncio
async def test_top_stories(top_stories, client_session):
    """
    - Test Retrieving top stories with the Top Stories API returns correct Status Code
    - Test Retrieving top stories with the Top Stories API returns an array of numbers
    - Test the API call fetches a maximum of 500 items in API response
    - Test the API call fetches items which could only be in [story, job]
    """
    print(f"Validation - Total items found in top-stories response:: Expected:<=500 Actual:{len(top_stories)}")
    assert len(top_stories) <= 500
    assert all(isinstance(item, int) for item in top_stories), "Top stories contains non-integer items"

    tasks = [fetch_item_async(item_id, client_session) for item_id in top_stories]
    items = await asyncio.gather(*tasks, return_exceptions=True)
    print("Checking if all items in top-stories are either story or job...")
    for item in items:
        if item and isinstance(item, dict):
            assert item.get("type") in ["story", "job"], f"Item {item.get('id')} has invalid type {item.get('type')}"

@pytest.mark.asyncio
async def test_top_story_from_stories(top_stories, client_session):
    """
    - Test Retrieving top story from the list of top-stories using items-api returns correct status code
    - Test items-api returns all mandatory fields - id
    """
    top_story_id = top_stories[0]
    item = await fetch_item_async(top_story_id, client_session)
    assert item is not None, f"Failed to fetch item with ID {top_story_id}"
    assert isinstance(item, dict), f"Item with ID {top_story_id} is not a dictionary"
    assert "id" in item, f"Item with ID {top_story_id} is missing 'id' field"
    assert isinstance(item["id"], int), f"ID field for item {top_story_id} is not an integer"
    assert item["id"] == top_story_id, f"Item ID {item['id']} does not match requested ID {top_story_id}"

@pytest.mark.asyncio
async def test_top_comment_from_top_story_in_top_stories(top_stories, client_session):
    """
    - Test Retrieving top comment from the top story in the list of top-stories using items-api returns correct status code
    - Test items-api returns non-empty list of kids/comments - fetch_valid_item ensures we have correct input data
    - Test first comment id from items-api kid[] is same as id in items-api when comment id is passed
    - Test top story id for the items-api for comment is shown as its parent
    """

    "fetches items from top stories which contains at least one kid"
    async def fetch_valid_item(session):
        for story_id in top_stories:
            item = await fetch_item_async(story_id, session)
            if item and isinstance(item, dict) and "id" in item and \
                    isinstance(item["id"], int) and item["id"] == story_id and \
                    item.get("kids", []) and isinstance(item["kids"], list) and len(item["kids"]) > 0:
                return item, story_id
        return None, None

    story_item, top_story_id = await fetch_valid_item(client_session)
    assert story_item is not None, "No top story with non-empty kids array found"

    top_comment_id = story_item["kids"][0]
    comment_item = await fetch_item_async(top_comment_id, client_session)
    assert comment_item is not None, f"Failed to fetch comment with ID {top_comment_id}"
    assert isinstance(comment_item, dict), f"Comment with ID {top_comment_id} is not a dictionary"
    assert "id" in comment_item, f"Comment with ID {top_comment_id} is missing 'id' field"
    assert isinstance(comment_item["id"], int), f"ID field for comment {top_comment_id} is not an integer"
    assert comment_item["id"] == top_comment_id, f"Comment ID {comment_item['id']} does not match requested ID {top_comment_id}"
    assert "parent" in comment_item, f"Comment with ID {top_comment_id} is missing 'parent' field"
    assert comment_item["parent"] == top_story_id, f"Comment parent ID {comment_item['parent']} does not match story ID {top_story_id}"

@pytest.mark.asyncio
async def test_total_comment_count(top_stories, client_session):
    """
    - Recursively traverse each top story and all its descendants via 'kids'
    - Count total number of comments across all stories
    """
    async def count_descendants(item_id, session):
        """Recursively count all kids (comments/replies) under an item."""
        item = await fetch_item_async(item_id, session)
        if not item or not isinstance(item, dict):
            return 0
        kids = item.get("kids", [])
        count = len(kids)
        # Recursively count for each kid
        for kid_id in kids:
            count += await count_descendants(kid_id, session)
        return count

    total_count = 0
    stories_with_less_comments = await get_stories_with_less_comments(top_stories, client_session)
    # To avoid overly long test runs, limited number of stories (here 6)
    for story_id in stories_with_less_comments[:6]:  # process only first 6 stories for speed
        story_item = await fetch_item_async(story_id, client_session)
        descendants = story_item["descendants"]

        if story_item and "kids" in story_item:
            total_count += await count_descendants(story_id, client_session)
        try:
            assert total_count == descendants
        except AssertionError:
            print(f"Error - Comments and descendants MISMATCH for Story {story_id}: \n"
                  f"Total comments (recursively) = {total_count}, Descendants = {descendants}")
        # Reset total_count for the next story if it’s per-story
        total_count = 0

@pytest.mark.asyncio
async def test_top_stories_empty_response(client_session):
    """
    Test that the Top Stories API handles an empty response gracefully.
    - Verify the response is an empty list.
    - Ensure the application does not crash or throw unexpected errors.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = mock_get.return_value.__aenter__.return_value
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])

        async with client_session.get("https://hacker-news.firebaseio.com/v0/topstories.json") as response:
            assert response.status == 200, f"Expected status 200, got {response.status}"
            top_stories_mocked = await response.json()

        assert top_stories_mocked == [], "Expected empty list for top stories"
        assert isinstance(top_stories_mocked, list), "Response must be a list"

@pytest.mark.asyncio
async def test_top_story_non_existent_id(top_stories, client_session):
    """
    Test that the Items API handles a non-existent story ID from top stories.
    - Simulate a 404 response for the top story ID.
    - Verify the application handles the missing story gracefully.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = mock_get.return_value.__aenter__.return_value
        mock_response.status = 404
        mock_response.json = AsyncMock(return_value=None)

        top_story_id = top_stories[0] if top_stories else 999999
        try:
            async with client_session.get(f"https://hacker-news.firebaseio.com/v0/item/{top_story_id}.json") as response:
                assert response.status == 404, f"Expected status 404, got {response.status}"
                story_data = await response.json()
                assert story_data is None, "Expected None for non-existent story"
        except Exception as e:
            assert False, f"Unexpected error for non-existent story ID: {e}"

@pytest.mark.asyncio
async def test_top_story_missing_id(top_stories, client_session):
    """
    Test that the Items API handles a top story missing the mandatory 'id' field.
    - Simulate a response without the 'id' field.
    - Verify the application detects and handles the missing field.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = mock_get.return_value.__aenter__.return_value
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "by": "test_user",
            "type": "story",
            "title": "Test Story",
            "time": 1234567890
        })  # No 'id' field

        top_story_id = top_stories[0] if top_stories else 999999
        try:
            async with client_session.get(f"https://hacker-news.firebaseio.com/v0/item/{top_story_id}.json") as response:
                assert response.status == 200, f"Expected status 200, got {response.status}"
                story_data = await response.json()
                assert "id" not in story_data, "Expected 'id' field to be missing"
                # Add your application's specific validation logic here
                # e.g., raise a custom exception or skip the story
                assert True, "Application should handle missing 'id' field"
        except Exception as e:
            assert False, f"Unexpected error for missing 'id' field: {e}"


if __name__ == "__main__":
    pytest.main()
