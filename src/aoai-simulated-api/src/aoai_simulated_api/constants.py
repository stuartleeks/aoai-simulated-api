#################################################################################
# context.values keys
# These are keys for 'well-known' values stored in the context.values dictionary.

# SIMULATOR_KEY_OPERATION_NAME stores the name of the OpenAI operation performed (e.g. embeddings, completion)
SIMULATOR_KEY_OPERATION_NAME = "Operation-Name"

# SIMULATOR_KEY_DEPLOYMENT_NAME stores the name of the OpenAI deployment used
SIMULATOR_KEY_DEPLOYMENT_NAME = "Deployment-Name"

# SIMULATOR_KEY_LIMITER stores the name of the limiter used for the request
# For built-in generators/forwarders this is 'openai'),
# but this allows additional limiters to be added via extensions
SIMULATOR_KEY_LIMITER = "Limiter"

# SIMULATOR_KEY_OPENAI_PROMPT_TOKENS stores the number of tokens used for the prompt
SIMULATOR_KEY_OPENAI_PROMPT_TOKENS = "XOpenAI-Tokens-Prompt"

# SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS stores the number of tokens used for the completion (i.e. generated tokens)
SIMULATOR_KEY_OPENAI_COMPLETION_TOKENS = "XOpenAI-Tokens-Completion"

# SIMULATOR_KEY_OPENAI_TOTAL_TOKENS stores the total number of tokens used in the request
SIMULATOR_KEY_OPENAI_TOTAL_TOKENS = "XOpenAI-Tokens-Total"


# TARGET_DURATION_MS stores the target duration of the request in milliseconds
# For recorded requests this will be the recorded duration
# For generated requests this will be estimated based on the request type and response length
TARGET_DURATION_MS = "Simulator-Target-Duration"
