# agentic-dotfiles

Starting to version control my agentic coding dotfiles as I start to feel the pain tracking them across projects.


## Option #1: Submodule

### Setup

```sh
git submodule add https://github.com/neozenith/agentic-dotfiles.git .claude
```

### Update

```sh
git submodule ...?? 🤷🏻‍♂️
```

## Option #2: gitignored clone

### Setup

`.gitignore`

```gitignore
.claude/
```

Then clone this repo into the gitignored folder:

```sh
git clone https://github.com/neozenith/agentic-dotfiles.git .claude
```

### Update

```sh
cd .claude
git pull
```