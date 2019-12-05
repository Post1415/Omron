import React from 'react';
import { CSVLink, CSVDownload } from "react-csv";

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = { value: '' };
  }  

  handleChange = (event) => {
    this.setState({ value: event.target.value });
  }

  render() {
    const Data = [
      ['Token'],
      [this.state.value]
    ];    

    return (
      <form>
        <label>
          <h1>TokenKey</h1>
          <input type="text" value={this.state.value} onChange={this.handleChange} />
        </label>
        <p>
        <button>
        <CSVLink data={Data} filename={"Token.csv"}>
        Submit
        </CSVLink>
        </button>
        </p>
      </form>
    );
  }
}
export default App;