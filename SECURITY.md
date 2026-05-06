# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it privately by emailing **eugen-goebel@hotmail.de**.

Please do not file public GitHub issues for security vulnerabilities, as this could expose users to risk before a fix is available.

## Response Time

I aim to acknowledge reports within 7 days and provide an initial assessment within 14 days.

## Supported Versions

This is a portfolio project; only the latest commit on `main` is supported.

## Note on Financial Data

This project deals with personal finance data. All sample data in the repository is synthetic (fictional merchants and amounts). When using the application:
- Never commit your real `finance.db` (it is gitignored)
- Use environment variables for any production configuration
- Be cautious when sharing exported reports
