# About

STM32CubeIde projects by default mix auto-generated code with user code, which might make it harder to diff.
User code is delimited by `/* USER CODE BEGIN */ /* USER CODE END */` comments, which this script can automatically
extract.

# Usage

```
usage: stm32cube_grovel [-h] (-p | -x | -r) [source_dir] [rebase_target]

Extracts /* USER CODE BEGIN */ ... /* USER CODE END */ snippets from STM32CubeIde Projects

positional arguments:
source_dir
rebase_target

options:
-h, --help       show this help message and exit
-p, --print-all  Print all user code snippets along with their filenames
-x, --extract    Extract all user code snippets in place into $BASENAME_snippet.$EXT files in the project
-r, --rebase     Take all _snippet.$EXT files and use them to replace the corresponding snippets in rebase_target

Copyright (C) 2022 Nikita Bloshchanevich
```

# Requirements

- Python 3, only standard libraries