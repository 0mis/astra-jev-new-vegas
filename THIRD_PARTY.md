# External components

- **Fallout: New Vegas**, owned by its respective rights holders. Obtain it separately. No game files, game art, game audio, saves or executable modifications are distributed here.
- **Typesafe Jev**, a hosted decision model. [Models](https://docs.typesafe.ai/models), [API](https://docs.typesafe.ai/api), [Choice](https://docs.typesafe.ai/primitives/choice). The client uses `jev-1.13.0`; access and service costs are separate from this source license.
- **xNVSE/NVSE** public layout research, pinned to commit [`3ff1e21d146e626eb71552af9f1ad381e7f943dd`](https://github.com/xNVSE/NVSE/tree/3ff1e21d146e626eb71552af9f1ad381e7f943dd). The observer's layout facts were checked against GameObjects.h, GameUI.h/cpp, GameTiles.h/cpp, GameForms.h and GameTypes.h. No xNVSE source files or binaries are bundled and no xNVSE installation is required for the current observer.
- **imageio-ffmpeg**, **FFmpeg**, **SoundCard** and **NumPy** are installed separately through the requirements. They retain their own licenses. FFmpeg build configuration determines its applicable license; this repository does not redistribute a compiled FFmpeg binary.

The MIT license applies only to this repository's original source and documentation.

- JIP LN NVSE primary layout research: https://github.com/jazzisparis/JIP-LN-NVSE (GameForms.h and internal/netimmerse.h for navmesh, world camera and scene graph fields). Layout facts were implemented independently; no source bundle or plugin is distributed here. No JIP installation is required.
# Design research: Minecraft agent

The user supplied https://github.com/rmalde/minecraft-agent . Design review used commit `78b40ed59514e5e2abde33a05ce398ecb2c39e05`: its async planner, compact observations, bounded pathfinding actions, action filtering and failure feedback informed the architecture. The New Vegas Python implementation is original; no source from that repository is copied or bundled. GitHub reported no license metadata at review time. The referenced Minecraft result uses a surveyed seed, Mineflayer and game-specific skills; its speed and cost are not New Vegas performance claims.
