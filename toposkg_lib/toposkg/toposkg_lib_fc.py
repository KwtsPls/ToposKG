import json
from openai import OpenAI
from openai.types.responses import ResponseOutputMessage, ResponseFunctionToolCall
from toposkg.toposkg_lib_core import KnowledgeGraphBlueprintBuilder, KnowledgeGraphSourcesManager

class FunctionCallingController:
    def __init__(self, openai_api_key: str, data_sources_repositories = []):
        self.openai_api_key = openai_api_key
        self.client = OpenAI(api_key=self.openai_api_key)
        self.chat_history = []

        self.sources_manager = KnowledgeGraphSourcesManager(data_sources_repositories)
        self.builder = None

        self. tools = [
            {
                "type": "function",
                "name": "source_manager_add_data_sources_from_repository",
                "description": "Explore a directory that includes data sources and add them to the list available of data sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sources_repository": {
                            "type": "string",
                            "description": "The path to the directory that contains the data sources."
                        }
                    },
                    "required": [
                        "sources_repository"
                    ],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "source_manager_get_source_paths",
                "description": "Get a list of paths to the available data sources.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "builder_set_name",
                "description": "Set the export name for the Knowledge Graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name that will be given to the Knowledge Graph."
                        }
                    },
                    "required": [
                        "name"
                    ],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "builder_set_output_dir",
                "description": "Set the output directory for the Knowledge Graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "output_dir": {
                            "type": "string",
                            "description": "The directory where the Knowledge Graph will be saved."
                        }
                    },
                    "required": [
                        "output_dir"
                    ],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "builder_add_source_path",
                "description": "Add the file on the given path to the list of files that will be used to construct the Knowledge Graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": "The path to the file that will be added to the list of files that will constitute the Knowledge Graph."
                        }
                    },
                    "required": [
                        "source_path"
                    ],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "builder_remove_source_path",
                "description": "Remove the file on the given path to the list of files that will be used to construct the Knowledge Graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source_path": {
                            "type": "string",
                            "description": "The path to the file that will be removed from the list of files that will constitute the Knowledge Graph."
                        }
                    },
                    "required": [
                        "source_path"
                    ],
                    "additionalProperties": False
                }
            },
            {
                "type": "function",
                "name": "builder_build",
                "description": "Create the Knowledge Graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    },
                    "additionalProperties": False
                }
            }
        ]

    def call_function(self, name, args):
        if name == "source_manager_add_data_sources_from_repository":
            self.sources_manager.add_data_sources_from_repository(args['sources_repository'])
            return "Added data sources from repository: " + args['sources_repository']
        if name == "source_manager_get_source_paths":
            return self.sources_manager.get_source_paths()
        if name == "builder_set_name":
            if self.builder is None:
                self.builder = KnowledgeGraphBlueprintBuilder()
            self.builder.set_name(args["name"])
            return "Name set to " + args["name"]
        if name == "builder_set_output_dir":
            if self.builder is None:
                self.builder = KnowledgeGraphBlueprintBuilder()
            self.builder.set_output_dir(args["output_dir"])
            return "Output directory set to " + args["output_dir"]
        if name == "builder_add_source_path":
            if self.builder is None:
                self.builder = KnowledgeGraphBlueprintBuilder()
            self.builder.add_source_path(args["source_path"])
            return "Source path added: " + args["source_path"]
        if name == "builder_remove_source_path":
            if self.builder is None:
                self.builder = KnowledgeGraphBlueprintBuilder()
            self.builder.remove_source_path(args["source_path"])
            return "Source path removed: " + args["source_path"]
        if name == "builder_build":
            if self.builder is None:
                return "No builder initialized."
            blueprint = self.builder.build()
            try:
                return blueprint.construct(validate=False)
            except Exception as e:
                return f"Error constructing Knowledge Graph: {str(e)}. You must set valid output directory and name before building the Knowledge Graph."
        return None

    def respond_to_chat(self, user_input, print_output=True):
        self.chat_history += [{"role": "user", "content": user_input}]

        response = self.client.responses.create(
            model="gpt-4.1-mini",
            instructions="You are a natural language interface for a python library that creates a Knowledge Graph from individual data sources."
                         "You can call functions from the library to perform actions. You can also ask the user for more information if needed.",
            input=self.chat_history,
            tools=self.tools
        )

        if isinstance(response.output[0], ResponseOutputMessage):
            self.chat_history += [{"role": "assistant", "content": response.output[0].content[0].text}]
            print("Assistant: " + self.chat_history[-1]['content'])
        elif isinstance(response.output[0], ResponseFunctionToolCall):
            for tool_call in response.output:
                if tool_call.type != "function_call":
                    continue

                print(tool_call)

                name = tool_call.name
                args = json.loads(tool_call.arguments)

                result = self.call_function(name, args)
                self.chat_history.append(tool_call)
                self.chat_history.append({
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": str(result)
                })
                # print(self.chat_history[-1])

            response = self.client.responses.create(
                model="gpt-4.1-mini",
                input=self.chat_history,
                tools=self.tools,
            )
            try:
                self.chat_history += [{"role": "assistant", "content": response.output[0].content[0].text}]
                if print_output:
                    print("Assistant: " + self.chat_history[-1]['content'])
            except Exception as e:
                pass

if __name__ == "__main__":
    fc = FunctionCallingController("YOUR_OPENAI_API_KEY", 'https://toposkg.di.uoa.gr')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            break
        fc.respond_to_chat(user_input, print_output=True)