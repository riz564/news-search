Feature: Ingress rate limiting
  Scenario: Exceed per-minute limit
    Given the API server is running on port 8091 with offline mode
    And a per-minute limit of 3 requests
    And I use the bearer token "test-secret"
    When I call "/search?query=apple&page=1&page_size=10&offline=0" 4 times within a minute
    Then the last response code is 429
