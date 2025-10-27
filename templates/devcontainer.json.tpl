{
  "name": "Android Dev Container - __PROJECT_NAME__",
  "image": "android-dev-base:latest",
  "workspaceFolder": "/workspace",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-azuretools.vscode-docker",
        "ms-vscode.cpptools",
        "msjsdiag.vscode-react-native"
      ]
    }
  },
  "mounts": [
    "source=${localWorkspaceFolder},target=/workspace,type=bind,consistency=cached"
  ],
  "remoteEnv": {
    "OPENAI_API_KEY": "${localEnv:OPENAI_API_KEY}",
    "ADB_SERVER_SOCKET": "tcp:host.docker.internal:5037"
  },
  "runArgs": [
    "--add-host=host.docker.internal:host-gateway"
  ]
}
