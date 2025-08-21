Feature: Search news
  As an API consumer
  I want to search news
  So that I can get normalized results quickly

  Scenario: Successful search with valid token
    Given the API server is running on port 8090 with offline mode
    And I use the bearer token "test-secret"
    When I GET "/search?query=apple&page=1&page_size=10&offline=0"
    Then the response code is 200
    And the JSON has keys "items", "total_estimated_pages", "time_taken_ms"
