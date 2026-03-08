from setuptools import setup, find_packages

setup(
    name="code-stash",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "console_scripts": [
            "code-stash=code_stash:main",
        ],
    },
    python_requires=">=3.8",
)
