all:	banker.wasm

%.wasm: %.cpp %.contracts.md %.clauses.md
	eosio-cpp -o $@ ${@:%.wasm=%.cpp}
