#include <eosio/eosio.hpp>
#include <eosio/asset.hpp>
#include <eosio/system.hpp>

using namespace eosio;

class [[eosio::contract("banker")]] banker : public eosio::contract {
  public:
    using contract::contract;

    banker(name receiver, name code, datastream<const char*>ds) :
        contract(receiver, code, ds) {

      account_index accounts(get_self(), get_self().value);
      accounts.emplace(vault, [&](auto& row) {
        row.key = vault;
        row.last_interest_timestamp = now();
        row.interest_bearing = false;
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
          row.last_interest_timestamp = now();
          row.interest_bearing = true;
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

      do_individual_interest(iterator, now());
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

        uint32_t sync = now();
        uint64_t interest = do_individual_interest(iterator, sync, false);

        accounts.modify(iterator, from, [&](auto& row) {
          row.balance[t_name] += quantity;
          row.balance[CP].amount += interest;
          row.last_interest_timestamp = sync;
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
      
      check(get_value(user_it->balance) >= amount,
            "Sorry, you don't have that much to withdraw.");
      check(get_value(vault_it->balance) >= amount,
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

        action(
          permission_level {get_self(), "active"_n},
          "eosio.token"_n,
          "transfer"_n,
          std::make_tuple(get_self(), user, coin, std::string("N/A"))
        ).send();
      }
    }

    [[eosio::action]]
    void setinterest(uint64_t rate) {
      require_auth(system_account);

      action(
        permission_level {system_account, "active"_n},
        get_self(),
        "calcinterest"_n,
        std::make_tuple()
      ).send();

      interest_rate = double(rate) / 10000.0;
    }

    [[eosio::action]]
    void calcinterest() {
      require_auth(system_account);

      uint32_t sync = now();

      account_index accounts(get_self(), vault.value);
      auto vault_it = accounts.find(vault.value);
      token_balance vault_balance;

      for (auto iterator = accounts.begin();
           iterator != accounts.end(); iterator++) {
        if(!iterator->interest_bearing) {
          continue;
        }

        do_individual_interest(iterator, sync);
      }
    }

    [[eosio::action]]
    void sendreserve() {
      require_auth(system_account);

      account_index accounts(get_self(), vault.value);
      auto vault_it = accounts.find(vault.value);

      for(int i = CP; i < MAX_TOKEN; i++) {
        const eosio::asset& coin = vault_it->balance[i];
        eosio::asset request;
        int64_t delta = desired_float / base_value[i] - coin.amount;
        if(delta == 0) {
          continue;
        }

        if(delta > 0) {
          // We need more coins
          request = asset(delta, coin.symbol);
          action(
            permission_level {get_self(), "active"_n},
            "eosio.token"_n,
            "transfer"_n,
            std::make_tuple(system_account, get_self(), request,
                            std::string("Reserve deposit"))
          ).send();
        } else {
          // We have too many coins
          request = asset(-delta, coin.symbol);
          action(
            permission_level {get_self(), "active"_n},
            "eosio.token"_n,
            "transfer"_n,
            std::make_tuple(get_self(), system_account, coin,
                            std::string("Reserve withdrawl"))
          ).send();
        }
      }
    }

  private:
    enum token_names {
      CP = 0,
      SP,
      EP,
      GP,
      PP,
      MAX_TOKEN
    };

    typedef eosio::asset token_balance[MAX_TOKEN];

    struct [[eosio::table]] bank_account {
      name key;

      token_balance balance;
      bool interest_bearing;
      uint32_t last_interest_timestamp;

      uint64_t primary_key() const { return key.value; };
    };

    typedef eosio::multi_index<"accounts"_n, bank_account> account_index;

    double interest_rate;  // In 1/100 of a percent, per-annum
    const double year = 365.25 * 24.0 * 3600.0;
    const uint64_t desired_float = 1000000;

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

    uint64_t get_value(const token_balance& balance) {
      uint64_t total = 0;
      for(int i = CP; i < MAX_TOKEN; i++) {
        total += balance[i].amount * base_value[i];
      }
      return total;
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

    uint32_t now() {
      return current_time_point().sec_since_epoch();
    }

    uint64_t do_individual_interest(account_index::const_iterator iterator,
                                    uint32_t sync, bool update=false) {
      int32_t duration = sync - iterator->last_interest_timestamp;
      if(duration < 0) {
        duration = 0;
      }

      double years = double(duration) / year;
      uint64_t total = get_value(iterator->balance);
      uint64_t interest = uint64_t(double(total) * years * interest_rate);

      if(interest > 0 && update) {
        account_index accounts(get_self(), iterator->key.value);
        accounts.modify(iterator, iterator->key, [&](auto& row) {
          row.last_interest_timestamp = sync;
          row.balance[CP].amount += interest;
        });
      }

      return interest;
    }
};

// vim:ts=2:sw=2:ai:et:si:sts=2
