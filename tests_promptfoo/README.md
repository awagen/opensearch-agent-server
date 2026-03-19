### Promptfoo Getting Started
Short descriptions to directly run evals. See more context below.

- install promptfoo (global install cmd): `npm install -g promptfoo`
- NOTE: config as relevant for generate and evaluate are done in the `promptfooconfig_*.yaml`
- (optional) set python executable (should work without): `export PROMPTFOO_PYTHON=[path to python]`
- in `tests_redteaming` folder, create .env with env vars:
  - `AWS_BEARER_TOKEN_BEDROCK`
  - `AG_UI_HOST`
  - `AG_UI_PORT`
- no need to call generate, generated examples can be found at:
  - `./eval_configs/redteam/small_engl/eval.yaml` (116 test cases)
  - `./eval_configs/redteam/medium_engl/eval.yaml` (> 200 cases)
  - `./eval_configs/redteam/medium_engl_german/eval.yaml`
- in case you want to regenerate (such as after changes to promptfooconfig.yaml), run: `ptomptfoo redteam generate [-c <promtfooconfig gile>]  [-o <output-filename>] [--verbose]`
- start up the ag ui server
- run eval via: `promptofoo redteam eval [-c <filename>] [--verbose] [--output <filename>.<json|xml|csv|html>]`
  - picks up the prompts and expectations on responses from the input filename (defaulting to redteam.yaml) and runs it
    on the app endpoint, parses response and has it evaluated by an LLM judge
  - the endpoint requested is configured in the `targets` config of the `promptfooconfig.yaml`. Here a python file is configured. Promptfoo 
    looks for existence of certain methods (e.g `call_api`) to invoke for each prompt to evaluate.
- after run is complete, can view results via `promptfoo view`
- the functional test cases can be run without generate step before, such as:
  - `promptfoo eval -c ./eval_configs/functional/multi_turn/functional_eval.yaml --output ./eval_configs/functional/multi_turn/results/fct_multiturn_eval_result.json`
  - `promptfoo eval -c ./eval_configs/functional/single_turn/functional_eval.yaml --output ./eval_configs/functional/single_turn/results/fct_singleturn_eval_result.json`


### Helper Scripts
You can find some helper scripts in the scripts folder. The scripts make some assumptions about the folder
structure. Within the `tests_promptfoo` root, all data will be generated inside the `eval_configs` subfolder, where you 
can find the folders:
- `functional` for functional tests
- `redteam` for redteam tests 
Each folder within these folders contains:
- its own test suite as yaml: `eval.yaml`
- `results` folder to store results of past runs

The available scripts are:
- Running available tests: `./scripts/run_eval.sh -k [TYPE of test, e.g 'functional' or 'redteam'] -t [TEST_SUITE_NAME, e.g single_turn] [-b; OUTPUT_BASE_NAME, e.g the eval result filename without format suffix] [-f; formats, comma separated if multiple, e.g html,xml,json,jsonl,csv] [-h for usage] [-d if overwrite]`
  - example: `./scripts/run_eval.sh -k functional -t single_turn`
- Generating redteam tests (to make them available tests that can be run): `./scripts/run_redteam_generate.sh -t [TEST_SUITE_NAME, e.g medium_german] [-c input_config, default is promptfooconfig_redteam.yaml in root test folder] [-h for usage] [-d if overwrite]`
  - example: `./scripts/run_redteam_generate.sh -t test` (picks the current promptfooconfig_redteam.yaml in the root test folder and generates the test cases into the respective redteam test suite folder in the `test` subfolder)
- Syncing the results of last run to the server: `./scripts/upload_last_results.sh`
  - NOTE that this will require you to have two env vars set up with the correct basic auth credentials:
    - export PROMPTFOO_SHARE_USERNAME=<username>
    - PROMPTFOO_SHARE_PASSWORD=<pwd>


### Sharing Data With Self-Hosted Eval Instance
Link: `https://www.promptfoo.dev/docs/usage/self-hosting/`
Two options:
- permanent config in promptfooconfig.yaml:
  """
  sharing:
    apiBaseUrl: http://your-server-address:3000
    appBaseUrl: http://your-server-address:3000
  """
- env vars: 
  """
  export PROMPTFOO_REMOTE_API_BASE_URL=http://your-server-address:3000
  export PROMPTFOO_REMOTE_APP_BASE_URL=http://your-server-address:3000
  """
  - here you will still need to call `promptfoo share` or combine eval with share as in `promptfoo eval --share`
- passing env vars with the cmd:
  - `PROMPTFOO_REMOTE_API_BASE_URL=http://your-server-address:3000 PROMPTFOO_REMOTE_APP_BASE_URL=http://your-server-address:3000 promptfoo share`


### Notes on conversationId and runId in test settings
- in multi-turn tests, make sure to keep the same conversationId between the turns
- for single-turn tests, even if conversationId changes, make sure to not set the runId, as this will cache responses and leave those tests out for which the result is already available


### On Result Persistence
Do not check in the single result files in case you generate them. In the result files apiKeys can possibly appear
resolved to clear text, and thus here result folders (as automatically used when using the scripts) are 
currently included in the `.gitignore` settings.
Use upload to eval server for sharing (see scripts folder).


### Caution When Deploying A Promptfoo Eval Server
Do not publicly expose the server with own provider keys (e.g OpenAI) as currently its possible to create evaluations with configured providers,
so anyone could configure this and run their own evals, which might be expensive.
Better: do not expose fully publicly anyways but restrict to fixed (VPN) IPs only  :).


### HTTP Api Reference: 
- https://www.promptfoo.dev/docs/api-reference


### Example Overview Of Results (Eval Server)
![Eval Multiturn](./images/example_multiturn.png)
![Redteam Eval Small](./images/example_redteam_small_engl.png)
![Redteam Eval Medium](./images/example_redteam_medium_engl.png)


### General commands
- (optional) `promptfoo redteam init`
- `promptfoo redteam run` (combines `redteam generate [-o <filename>]` and `redteam eval [-c <file-generated-by-generate-cmd>]`): generate adversarial test cases and run them against the target
  - generates selected test cases
    - Requests attck from cloud service, using the configured provider (or uses default openai:gpt-5-2025-08-07) (https://www.promptfoo.dev/docs/red-team/architecture/)
    - Generated attacks are based on configured plugins and strategies
  - runs test cases and stores results in db in ~/.promptfoo/
    - client runs attacks against target system and evaluates responses
    - testing finishes if vulnerability detected, otherwise follow-up attacks w context from previous attempts
    - promptfoo promises increasingly sophisticated attacks (e.g see also jailbreak:meta strategy)
    - max attempt limit allows controlling of the nr of attacks filed
  - generates result summary and exposes results via html view via `promtfoo view` / `promptfoo redteam report`
    - detailled results about fails / sucessful runs
  - puts `redteam.yaml` in current folder containing all generated test cases (or in any other file when using output option  `-o [filename.yaml]`)
- full list of redteam plugins: `promptfoo redteam plugins`


### Bedrock for adversarial prompt generation
- `https://www.promptfoo.dev/docs/providers/aws-bedrock/`
- auth options see `https://www.promptfoo.dev/docs/providers/aws-bedrock/#authentication-options`
- install `@aws-sdk/client-bedrock-runtime` via: `npm install @aws-sdk/client-bedrock-runtime`
  - sdk pulls credentials from locations
    - IAM roles if on EC2
    - ~/.aws/credentials
    - AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars
- NOTE: whatever you do here, never configure any credentials in the promptfoo config!
  Not even via templating language and env.ENV_VAR_NAME reference, since during prompt generation 
  and eval this gets resolved and then the key leaks into all exports of results to server and 
  the local result files (thus the .gitignore addition)
```yaml
providers:
  - id: bedrock:anthropic.claude-3-5-sonnet-20241022-v2:0
    config:
      region: 'us-west-2'
      max_tokens: 256
      temperature: 0.7
```
- can also use the `BEDROCK_INFERENCE_PROFILE_ARN`
```yaml
providers:
  # Claude Opus 4.6 via global inference profile (required for this model)
  - id: bedrock:arn:aws:bedrock:us-east-2::inference-profile/global.anthropic.claude-opus-4-6-v1
    config:
      inferenceModelType: 'claude'
      region: 'us-east-2'
      max_tokens: 1024
      temperature: 0.7

  # Using an inference profile that routes to Claude models
  - id: bedrock:arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/claude-profile
    config:
      inferenceModelType: 'claude'
      max_tokens: 1024
      temperature: 0.7
      anthropic_version: 'bedrock-2023-05-31'
```
- can also use `AWS_BEARER_TOKEN_BEDROCK` env var for simplified auth (limited to AWS Bedrock and AWS Bedrock runtime actions)
```bash
export AWS_BEARER_TOKEN_BEDROCK="your-api-key-here"
```
```yaml
providers:
  - id: bedrock:us.anthropic.claude-3-5-sonnet-20241022-v2:0
    config:
      region: 'us-east-1' # Optional, defaults to us-east-1
```
OR
```yaml
providers:
  - id: bedrock:us.anthropic.claude-3-5-sonnet-20241022-v2:0
    config:
      region: 'us-east-1' # Optional, defaults to us-east-1
```
- and more ... (see above provided link)

- Claude-specific settings
  - `https://www.promptfoo.dev/docs/providers/aws-bedrock/#claude-models`

  
### API Usage
The tool uses LLM endpoint (via api.promptfoo.app remote grading, using configured LLM) for 
- adversarial prompt generation, given the criteria
- given the response to the prompt, evaluate against criteria
- Question: can we fully deploy on own server or do we need official server as proxy?
  - own deployment possible for storing evals
  - inference server for remote prompt generation likely only for enterprise version
  - request flow in general:
    - promptfoo api involved in both generate and eval calls
      - for evals also passes the prompts returned from the app (!)


### Run Mode
Given the usage in both generation of prompt candidates and evaluation of LLM
responses, it makes sense to separate the generation of prompt candidates from the actual evaluation
- generate: `promptofoo redteam generate [-o <filename>] [-c <config-file>, default: promptfoo.yaml] [--verbose]` (less frequent)
- evaluate: `promptofoo redteam eval [-c <filename>] [--verbose]`
- view results: `promptfoo view`


### Attack Generation
- `https://www.promptfoo.dev/docs/red-team/configuration/#how-attacks-are-generated`
- by default, promptfoo uses local OpenAI key for attack generation and grading
- IF no key set, promptfoo proxies requests to their own API for generation and
  grading. The evaluation of target model is always performed locally.
- `redteam.provider` config controls both attack generation and grading (!!)
- Can enforce 100 % local generation by setting `PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION` env var to true.
  - this also disables promotfoos remote service optimized for generating adversarial inputs.
- Can also pass provider on the cmd line: `promptfoo redteam generate --provider openai:chat:gpt-5-mini`


### Data Sharing
- even if custom LLM provider is configured, you will see that some calls are made to 
  the promptfoo api. Details see here: `https://github.com/promptfoo/promptfoo/issues/5808`
  - details known to be send:
    - Instructions/prompts
    - Conversation history (messages)
    - User email (from getUserEmail())
    - Promptfoo version
    - System purpose description

Excerpt from above github issue:
```text
To clarify, Promptfoo is 100% local for LLM evaluations, and prompts always remain local.

Promptfoo does require remote generation for a subset of red team plugins, listed here. 
Any plugin with the globe icon requires remote inference. It is possible to self-host the inference endpoint as part of 
our enterprise offering. The "system purpose description" is used by the remote server to generate attacks. 
The target's prompt and other target configuration details are never sent.

As you mentioned, you can disable remote generation using export PROMPTFOO_DISABLE_REDTEAM_REMOTE_GENERATION=true. 
This would prevent you from generating attacks for a subset of plugins that rely on remote inference.
```

- Hosting urself is an option, but for the inference server this seems limited to the enterprise version
- Keys do not seem to leave local though
- fully local only when combining
  - a local provider (e.g ollama): `redteam.provider: ollama:chat:llama3.2`
  - disable remote generation: `PROMPTFOO_DISABLE_REMOTE_GENERATION`
- even when LLM provider is configured and attacks are available (e.g readteam.yaml), the eval call still calls the
  promptfoo api and sens the agent response. Seems to be only avoidable with options
  - fully local eval call (see above config)
  - alternative: enterprise deployment of own server
- recommendation by the team (`https://www.promptfoo.dev/docs/red-team/troubleshooting/grading-results/`):
  - use remote llm for generation of attacks
  - grading works well locally as well


### Non-redteam test cases
 - answer-relevance (functional eval): https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/answer-relevance/
 - llm-rubric (functional eval): https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric
 - pi (functional eval): https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/pi/
 - classifier (tone and so on): https://www.promptfoo.dev/docs/configuration/expected-outputs/classifier/
 - select-best (if wanting to compare several different providers): https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/select-best/
 - moderation (ensure safe outputs and compliance with usage policies): https://www.promptfoo.dev/docs/configuration/expected-outputs/moderation/
 - context-based (context-recall, context-relevance, context-faithfulness) (might be useful to check that on multi-step chat the context is enriched the right way via MCP and such)
  - https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/context-recall/
  - https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/context-relevance/
  - https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/context-faithfulness/ 
 - conversation-relevance (ensure responses remain relevant throughout a conversation): https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/conversation-relevance/
 - see example for multi-turn-conversation here: https://github.com/promptfoo/promptfoo/blob/main/examples/multiple-turn-conversation/promptfooconfig.yaml


