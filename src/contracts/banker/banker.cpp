#include <eosio/eosio.hpp>
#include <eosio/asset.hpp>

using namespace eosio;

class [[eosio::contract("banker")]] banker : public eosio::contract {
  public:
    using contract::contract;

    enum token_names {
      CP = 0,
      SP,
      EP,
      GP,
      PP,
      MAX_TOKEN
    };

    banker(name receiver, name code, datastream<const char*>ds) :
        contract(receiver, code, ds) {

      account_index accounts(get_self(), get_self().value);
      accounts.emplace(vault, [&](auto& row) {
        row.key = vault;
        for(int i = CP; i < MAX_TOKEN; i++) {
          row.balance[i] = eosio::asset(0, symbol_names[i]);
        }
      });
    }

    [[eosio::action]]
    void newaccount(name user) {
      require_auth(user);
      account_index accounts(get_self(), get_first_receiver().value);
      auto iterator = accounts.find(user.value);
      if(iterator == accounts.end()) {
        // The user isn't in the table
        accounts.emplace(user, [&](auto& row) {
          row.key = user;
          for(int i = CP; i < MAX_TOKEN; i++) {
            row.balance[i] = eosio::asset(0, symbol_names[i]);
          }
        });
      }
    }

    [[eosio::action]]
    void closeaccount(name user) {
      require_auth(user);
      account_index accounts(get_self(), get_first_receiver().value);
      auto iterator = accounts.find(user.value);
      check(iterator != accounts.end(), "Account does not exist");

      for(int i = CP; i < MAX_TOKEN; i++) {
        const eosio::asset& coin = iterator->balance[i];
        if(coin.amount == 0) {
          continue;
        }

        action {
          permission_level {get_self(), "active"_n},
          "eosio.token"_n,
          "transfer"_n,
          std::make_tuple(get_self(), user, coin, std::string("Account closing"))
        }.send();
      }
      accounts.erase(iterator);
    }

    [[eosio::on_notify("eosio.token::transfer")]]
    void deposit(name from, name to, eosio::asset quantity, std::string memo) {
      if (from == get_self() || to != get_self())
      {
        return;
      }

      check(quantity.amount > 0, "Nice try");

      auto token_it = token_map.find(quantity.symbol.raw());
      check(token_it != token_map.end(), "Nope, we don't take that kind of token");
      token_names t_name = token_it->second;

      account_index accounts(get_self(), from.value);

      if(from.value == system_account.value) {
        // this is a transfer from the system account (reserves) to the bank.
        // Just it in the vault.
      } else {
        auto iterator = accounts.find(from.value);
        check(iterator != accounts.end(), "Account does not exist");

        accounts.modify(iterator, from, [&](auto& row) {
          row.balance[t_name] += quantity;
        });
      }

      auto iterator = accounts.find(vault.value);
      accounts.modify(iterator, vault, [&](auto& row) {
        row.balance[t_name] += quantity;
      });
    }

    [[eosio::action]]
    void withdraw(name user, uint64_t amount) {
      require_auth(user);

      account_index accounts(get_self(), user.value);
      auto vault_it = accounts.find(vault.value);
      auto user_it = accounts.find(user.value);
      
      check(verify_value(user_it->balance, amount),
            "Sorry, you don't have that much to withdraw.");
      check(verify_value(vault_it->balance, amount),
            "Sorry, the vault doesn't contain that much, come back later");

      token_balance out_balance;
      remove_value(vault_it, amount, out_balance);

      token_balance who_cares;
      remove_value(user_it, amount, who_cares);

      for(int i = CP; i < MAX_TOKEN; i++) {
        eosio::asset& coin = out_balance[i];
        if(coin.amount == 0) {
          continue;
        }

        action {
          permission_level {get_self(), "active"_n},
          "eosio.token"_n,
          "transfer"_n,
          std::make_tuple(get_self(), user, coin, std::string("N/A"))
        }.send();
      }
    }

  private:
    typedef eosio::asset token_balance[MAX_TOKEN];

    struct [[eosio::table]] bank_account {
      name key;

      token_balance balance;

      uint64_t primary_key() const { return key.value; };
    };

    typedef eosio::multi_index<"accounts"_n, bank_account> account_index;

    const name system_account = name("mud.havokmud");
    const name vault = name("bank_vault");

    const symbol symbol_names[MAX_TOKEN] = {symbol("CP", 4), symbol("SP", 4),
                                            symbol("EP", 4),
                                            symbol("GP", 4), symbol("PP", 4)};
    const uint32_t base_value[MAX_TOKEN] = {1, 10, 50, 100, 1000};

    const std::map<uint64_t, token_names> token_map = {
      {symbol("CP", 4).raw(), CP}, 
      {symbol("SP", 4).raw(), SP}, 
      {symbol("EP", 4).raw(), EP}, 
      {symbol("GP", 4).raw(), GP}, 
      {symbol("PP", 4).raw(), PP}, 
    };

    bool verify_value(const token_balance& balance, uint64_t value) {
      uint64_t total = 0;
      for(int i = CP; i < MAX_TOKEN; i++) {
        total += balance[i].amount * base_value[i];
      }
      return total >= value;
    }

    void remove_value(account_index::const_iterator iterator,
                      uint64_t value, token_balance& out_coins) {
      account_index accounts(get_self(), get_self().value);
      const token_balance& balance = iterator->balance;
      accounts.modify(iterator, iterator->key, [&](auto& row) {
        for(int i = PP; i >= CP; i--) {
          uint64_t count = value / base_value[i];
          if(count > balance[i].amount) {
            count = balance[i].amount;
          }
          value -= count * base_value[i];

          row.balance[i].amount -= count;
          out_coins[i] = asset(count, symbol_names[i]);
        }
      });
    }
};

// vim:ts=2:sw=2:ai:et:si:sts=2
