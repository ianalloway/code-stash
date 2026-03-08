from setuptools import setup, find_packages

setup(
    name="code-stash",
    version="0.2.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "numpy",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "code-stash=code_stash:main",
        ],
    },
    python_requires=">=3.8",
)
