Team Number : 153
Description

This PR implements rate limiting middleware to prevent excessive or spam usage of the roast bot API endpoints. The feature ensures fair usage, improves backend stability, and protects the application from potential abuse or denial-of-service scenarios.

Related Issue

Closes #44

Type of Change

 Bug fix (non-breaking change which fixes an issue)

 New feature (non-breaking change which adds functionality)

 Breaking change (fix or feature that would cause existing functionality to not work as expected)

 Documentation update

 Code refactoring

 Performance improvement

 Style/UI improvement

Changes Made

Added rate limiting middleware to API endpoints

Configured request limits using environment variables

Implemented proper HTTP 429 (Too Many Requests) response handling

Added basic test cases to validate rate limiting behavior

Updated README with configuration instructions

Screenshots (if applicable)

Before:
No rate limiting — unlimited requests allowed.

After:
Returns HTTP 429 response when request limit is exceeded.

Testing

 Tested on Desktop (Chrome/Firefox/Safari)

 Tested on Mobile (iOS/Android)

 Tested responsive design (different screen sizes)

 No console errors or warnings

 Code builds successfully (npm run build)

Checklist

 My code follows the project's code style guidelines

 I have performed a self-review of my code

 I have commented my code where necessary

 My changes generate no new warnings

 I have tested my changes thoroughly

 All TypeScript types are properly defined

 Tailwind CSS classes are used appropriately (no inline styles)

 Component is responsive across different screen sizes

 I have read and followed the CONTRIBUTING.md
 guidelines