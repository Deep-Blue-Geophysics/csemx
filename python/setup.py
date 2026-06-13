from setuptools import find_packages, setup

setup(
    name="csemx",
    version="0.1.0",
    description="Client I/O and validation utilities for csemx bundles",
    package_dir={"": "src"},
    packages=find_packages("src"),
    package_data={"csemx": ["schemas/*.json"]},
    python_requires=">=3.9",
    extras_require={
        "full": [
            "PyYAML",
            "jsonschema",
            "pyproj",
            "pyarrow",
        ],
    },
    entry_points={
        "console_scripts": [
            "csemx=csemx.cli:main",
        ],
    },
)
